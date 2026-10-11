// Database, originals, removed originals and active pointer share one commit.
const LEASE_MS = 90000;

export class SnapshotConflict extends Error {
  constructor() {super('These records are open in another session.');this.name='SnapshotConflict';}
}
export class SnapshotWriteError extends Error {
  constructor(code='storage') {super('The records could not be saved.');this.name='SnapshotWriteError';this.code=code;}
}

function validateFiles(files) {
  if(!Array.isArray(files)) throw new SnapshotWriteError('invalid');
  const names = new Set();
  for(const file of files) {
    if(!file || typeof file.path!=='string' || !file.path || file.path.length>1024 ||
       file.path.startsWith('/') || /[\\\x00]/.test(file.path) ||
       file.path.split('/').some(part=>!part || part==='.' || part==='..') ||
       names.has(file.path) || !(file.bytes instanceof Uint8Array)) throw new SnapshotWriteError('invalid');
    names.add(file.path);
  }
}

async function digest(bytes) {
  const hash = await crypto.subtle.digest('SHA-256',bytes);
  return [...new Uint8Array(hash)].map(value=>value.toString(16).padStart(2,'0')).join('');
}

export class SnapshotStore {
  constructor(database) {this.database=database;}

  static open(name) {
    return new Promise((resolve,reject) => {
      const request=indexedDB.open(name,1);
      request.onupgradeneeded=()=>{
        request.result.createObjectStore('state');
        request.result.createObjectStore('files',{keyPath:'path'});
      };
      request.onsuccess=()=>resolve(new SnapshotStore(request.result));
      request.onerror=()=>reject(new SnapshotWriteError(request.error?.name));
      request.onblocked=()=>reject(new SnapshotWriteError('blocked'));
    });
  }

  transaction(action) {
    return new Promise((resolve,reject) => {
      let result, failure;
      let tx;
      try {tx=this.database.transaction(['state','files'],'readwrite');}
      catch(error) {reject(new SnapshotWriteError(error.name));return;}
      const answer=value=>{result=value;};
      const fail=error=>{failure=error;tx.abort();};
      tx.oncomplete=()=>resolve(result);
      tx.onabort=()=>reject(failure || new SnapshotWriteError(tx.error?.name));
      const read=tx.objectStore('state').get('current');
      read.onsuccess=()=>{
        const state=read.result || {generation:0,owner:null,lease:null,until:0,hashes:{}};
        try {action(tx,state,answer,fail);}
        catch(error) {fail(error instanceof SnapshotConflict ? error : new SnapshotWriteError(error.name));}
      };
    });
  }

  acquire(owner) {
    if(typeof owner!=='string' || !owner || owner.length>128) return Promise.reject(new SnapshotConflict());
    return this.transaction((tx,state,answer,fail) => {
      if(state.owner && state.owner!==owner && state.until>Date.now()) {fail(new SnapshotConflict());return;}
      const lease=crypto.randomUUID();
      tx.objectStore('state').put({...state,owner,lease,until:Date.now()+LEASE_MS},'current');
      const files=tx.objectStore('files').getAll();
      files.onsuccess=()=>answer({generation:state.generation,lease,files:files.result});
    });
  }

  async commit(owner,lease,expectedGeneration,files) {
    validateFiles(files);
    const hashes=Object.create(null);
    for(const file of files) hashes[file.path]=await digest(file.bytes);
    return this.transaction((tx,state,answer,fail) => {
      if(state.owner!==owner || state.lease!==lease || state.until<=Date.now() ||
         state.generation!==expectedGeneration) {fail(new SnapshotConflict());return;}
      const records=tx.objectStore('files');
      // Only changed bytes are written; the transaction still commits the
      // complete set atomically. Opening a page need not recopy every original.
      for(const name of Object.keys(state.hashes || {})) {
        if(!Object.hasOwn(hashes,name)) records.delete(name);
      }
      for(const file of files) {
        if(hashes[file.path]!==state.hashes?.[file.path]) records.put({path:file.path,bytes:file.bytes});
      }
      const generation=state.generation+1;
      tx.objectStore('state').put({...state,generation,hashes,until:Date.now()+LEASE_MS},'current');
      answer(generation);
    });
  }

  renew(owner,lease) {
    return this.transaction((tx,state,answer,fail) => {
      if(state.owner!==owner || state.lease!==lease || state.until<=Date.now()) {fail(new SnapshotConflict());return;}
      tx.objectStore('state').put({...state,until:Date.now()+LEASE_MS},'current');
    });
  }

  release(owner,lease) {
    return this.transaction((tx,state) => {
      if(state.owner===owner && state.lease===lease) {
        tx.objectStore('state').put({...state,owner:null,lease:null,until:0},'current');
      }
    });
  }
}

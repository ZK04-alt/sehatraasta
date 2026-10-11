// Storage tests use real Chromium IndexedDB, not an in-memory imitation.
import assert from 'node:assert/strict';
import {readFileSync, existsSync} from 'node:fs';
import http from 'node:http';
import {createRequire} from 'node:module';
import {resolve} from 'node:path';
import {test, before, after} from 'node:test';
const {chromium} = createRequire(import.meta.url)('playwright');
let browser, base;
const source = resolve('browser/storage.mjs');
const server = http.createServer((req,res) => {
  if(req.url==='/') {res.writeHead(200,{'Content-Type':'text/html'});return res.end('<!doctype html><title>Storage test</title>');}
  if(req.url==='/storage.mjs' && existsSync(source)) {
    res.writeHead(200,{'Content-Type':'text/javascript'});return res.end(readFileSync(source));
  }
  res.writeHead(404);res.end('Not found');
});
before(async () => {
  await new Promise(done=>server.listen(0,'127.0.0.1',done));
  base = 'http://127.0.0.1:'+server.address().port;
  browser = await chromium.launch({channel:'msedge',headless:true});
});
after(async () => {if(browser) await browser.close();await new Promise(done=>server.close(done));});
async function exercise(fn) {
  const page = await browser.newPage();
  try {
    await page.goto(base);
    await page.evaluate(async () => {globalThis.SnapshotStore=(await import('/storage.mjs')).SnapshotStore;});
    return await page.evaluate(fn);
  } finally {await page.close();}
}

test('test_atomic_snapshot',async () => {
  const result = await exercise(async () => {
    const name='atomic-'+crypto.randomUUID(), store=await SnapshotStore.open(name);
    const initial=await store.acquire('one');
    const generation=await store.commit('one',initial.lease,initial.generation,[
      {path:'sehatraasta.sqlite',bytes:new Uint8Array([1,2])},
      {path:'attachments/a.pdf',bytes:new Uint8Array([3,4])}]);
    const reopened=await SnapshotStore.open(name), saved=await reopened.acquire('one');
    return {generation,saved:saved.generation,files:saved.files.map(f=>[f.path,[...f.bytes]]).sort()};
  });
  assert.equal(result.generation,1);assert.equal(result.saved,1);
  assert.deepEqual(result.files,[['attachments/a.pdf',[3,4]],['sehatraasta.sqlite',[1,2]]]);
});

test('test_quota_failure_retains_previous',async () => {
  const result=await exercise(async () => {
    const name='quota-'+crypto.randomUUID(), store=await SnapshotStore.open(name), first=await store.acquire('one');
    await store.commit('one',first.lease,0,[{path:'db',bytes:new Uint8Array([1])}]);
    const put=IDBObjectStore.prototype.put;
    IDBObjectStore.prototype.put=function(value,...rest) {
      if(this.name==='files' && value.path==='new.pdf') throw new DOMException('Injected quota failure','QuotaExceededError');
      return put.call(this,value,...rest);
    };
    let failure;
    try {await store.commit('one',first.lease,1,[{path:'db',bytes:new Uint8Array([9])},{path:'new.pdf',bytes:new Uint8Array([8])}]);}
    catch(error) {failure=error.name;}
    finally {IDBObjectStore.prototype.put=put;}
    const saved=await (await SnapshotStore.open(name)).acquire('one');
    return {failure,generation:saved.generation,files:saved.files.map(f=>[f.path,[...f.bytes]])};
  });
  assert.equal(result.failure,'SnapshotWriteError');assert.equal(result.generation,1);
  assert.deepEqual(result.files,[['db',[1]]]);
});

test('test_stale_writer_rejected',async () => {
  const result=await exercise(async () => {
    const store=await SnapshotStore.open('stale-'+crypto.randomUUID()), first=await store.acquire('one');
    await store.commit('one',first.lease,0,[{path:'db',bytes:new Uint8Array([1])}]);
    const second=await store.acquire('one');
    let failure;
    try {await store.commit('one',first.lease,1,[{path:'db',bytes:new Uint8Array([9])}]);} catch(error){failure=error.name;}
    const saved=await store.acquire('one');
    return {failure,leaseChanged:first.lease!==second.lease,generation:saved.generation,bytes:[...saved.files[0].bytes]};
  });
  assert.equal(result.failure,'SnapshotConflict');assert.equal(result.leaseChanged,true);
  assert.equal(result.generation,1);assert.deepEqual(result.bytes,[1]);
});

test('test_second_tab_rejected',async () => {
  const result=await exercise(async () => {
    const name='tabs-'+crypto.randomUUID(), first=await SnapshotStore.open(name), lease=await first.acquire('one');
    await first.commit('one',lease.lease,0,[{path:'db',bytes:new Uint8Array([1])}]);
    const second=await SnapshotStore.open(name);
    let failure;
    try {await second.acquire('two');} catch(error){failure=error.name;}
    const saved=await first.acquire('one');
    return {failure,generation:saved.generation,bytes:[...saved.files[0].bytes]};
  });
  assert.equal(result.failure,'SnapshotConflict');assert.equal(result.generation,1);assert.deepEqual(result.bytes,[1]);
});

test('test_restore_snapshot_reopens',async () => {
  const result=await exercise(async () => {
    const name='restore-'+crypto.randomUUID(), store=await SnapshotStore.open(name), first=await store.acquire('one');
    await store.commit('one',first.lease,0,[{path:'db',bytes:new Uint8Array([1])}]);
    await store.commit('one',first.lease,1,[
      {path:'active-dataset',bytes:new TextEncoder().encode('restores/demo/sehatraasta.sqlite')},
      {path:'restores/demo/sehatraasta.sqlite',bytes:new Uint8Array([2])},
      {path:'restores/demo/attachments/demo.pdf',bytes:new Uint8Array([3])},
      {path:'removed/demo.pdf',bytes:new Uint8Array([4])}]);
    await store.release('one',first.lease);
    const saved=await (await SnapshotStore.open(name)).acquire('two');
    return {generation:saved.generation,paths:saved.files.map(f=>f.path).sort()};
  });
  assert.equal(result.generation,2);
  assert.deepEqual(result.paths,['active-dataset','removed/demo.pdf','restores/demo/attachments/demo.pdf','restores/demo/sehatraasta.sqlite']);
});

test('expired lease is fenced after another owner acquires',async () => {
  const result=await exercise(async () => {
    const clock=Date.now;let now=1000000;Date.now=()=>now;
    try {
      const store=await SnapshotStore.open('expiry-'+crypto.randomUUID()), first=await store.acquire('one');
      await store.commit('one',first.lease,0,[{path:'db',bytes:new Uint8Array([1])}]);
      now+=120000;const second=await store.acquire('two');
      let failure;
      try {await store.commit('one',first.lease,1,[{path:'db',bytes:new Uint8Array([9])}]);}catch(error){failure=error.name;}
      return {failure,generation:second.generation,bytes:[...second.files[0].bytes]};
    } finally {Date.now=clock;}
  });
  assert.equal(result.failure,'SnapshotConflict');assert.equal(result.generation,1);assert.deepEqual(result.bytes,[1]);
});

test('invalid snapshot path cannot change stored records',async () => {
  const result=await exercise(async () => {
    const store=await SnapshotStore.open('path-'+crypto.randomUUID()), first=await store.acquire('one');
    let rejected=0;
    for(const path of ['../outside','/absolute','a/../b','a\\b']) {
      try {await store.commit('one',first.lease,0,[{path,bytes:new Uint8Array([1])}]);}catch(error){rejected++;}
    }
    const saved=await store.acquire('one');return {rejected,generation:saved.generation,count:saved.files.length};
  });
  assert.deepEqual(result,{rejected:4,generation:0,count:0});
});

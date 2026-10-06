// Render selected original documents locally; never send them to a cloud renderer.
const status = document.querySelector('#report-status');
const button = document.querySelector('#report-print');
function documentCaption(section, number, count) {
  const patient = document.querySelector('.patient-heading h2').textContent;
  const details = document.querySelector('.patient-heading p').textContent;
  return patient+' · '+details+' · '+section.querySelector('h3').textContent+' · '+section.querySelector('.document-identity').textContent+' · '+section.querySelector('.document-source').textContent+' · '+number+'/'+count;
}
document.documentElement.dataset.reportReady = 'no';
button.addEventListener('click', () => {
  if (document.documentElement.dataset.reportReady !== 'yes') return;
  if (window.SRAndroid) window.SRAndroid.printDocument(); else window.print();
});
async function prepare() {
  let pdfjs;
  let pages = 0;
  let imageBytes = 0;
  const checkImage = source => {
    imageBytes += source.length;
    if (imageBytes > 33554432) throw new Error('choose fewer documents');
    return source;
  };
  for (const section of document.querySelectorAll('[data-document]')) {
    document.documentElement.dataset.reportStage = 'read-document';
    const container = section.querySelector('.document-pages');
    if (section.dataset.document === 'application/pdf' && window.SRAndroid) {
      const native = await fetch(section.dataset.nativeUrl, {cache:'no-store'});
      if (!native.ok) throw new Error('document unavailable');
      const result = await native.json();
      if (!Array.isArray(result.pages) || !result.pages.length || pages + result.pages.length > 60) throw new Error('page limit');
      for (let number=0; number<result.pages.length; number++) {
        const image = new Image(); image.src = checkImage(result.pages[number]);
        image.alt = section.querySelector('h3').textContent+' — '+(number+1); await image.decode();
        const figure = document.createElement('figure'); figure.className = 'document-page';
        const caption = document.createElement('figcaption'); caption.textContent = documentCaption(section,number+1,result.pages.length);
        figure.append(caption,image); container.append(figure); pages++;
      }
      continue;
    }
    const response = await fetch(section.dataset.url, {cache:'no-store'});
    if (!response.ok) throw new Error('document unavailable');
    const bytes = await response.arrayBuffer();
    if (section.dataset.document === 'application/pdf') {
      if (!pdfjs) {
        pdfjs = await import('./vendor/pdfjs/pdf.min.mjs');
        pdfjs.GlobalWorkerOptions.workerSrc = new URL('./vendor/pdfjs/pdf.worker.min.mjs', import.meta.url).href;
      }
      const root = new URL('./vendor/pdfjs/', import.meta.url).href;
      const task = pdfjs.getDocument({data:new Uint8Array(bytes), isEvalSupported:false,
        cMapUrl:root+'cmaps/', cMapPacked:true, standardFontDataUrl:root+'standard_fonts/',
        wasmUrl:root+'wasm/', useWasm:false, isImageDecoderSupported:false});
      const pdf = await task.promise;
      if (pages + pdf.numPages > 60) { await task.destroy(); throw new Error('too many pages'); }
      for (let number = 1; number <= pdf.numPages; number++) {
        const page = await pdf.getPage(number);
        const initial = page.getViewport({scale:1});
        const viewport = page.getViewport({scale:Math.min(2, 1600 / Math.max(initial.width, initial.height))});
        const canvas = document.createElement('canvas');
        canvas.width = Math.ceil(viewport.width); canvas.height = Math.ceil(viewport.height);
        await page.render({canvasContext:canvas.getContext('2d'), viewport, intent:'print'}).promise;
        const image = new Image(); image.alt = section.querySelector('h3').textContent + ' — ' + number;
        image.src = checkImage(canvas.toDataURL('image/png')); await image.decode();
        const figure = document.createElement('figure'); figure.className = 'document-page';
        const caption = document.createElement('figcaption');
        caption.textContent = documentCaption(section,number,pdf.numPages);
        figure.append(caption, image); container.append(figure);
        canvas.width = 0; canvas.height = 0; page.cleanup(); pages++;
      }
      document.documentElement.dataset.reportStage = 'release-pdf';
      await task.destroy();
    } else {
      document.documentElement.dataset.reportStage = 'read-image';
      if (++pages > 60) throw new Error('too many pages');
      const image = new Image(); image.alt = section.querySelector('.document-source').textContent;
      const data = new Uint8Array(bytes);
      // Data URLs survive Android's print adapter without public filesystem paths.
      let binary = ''; for (let start=0; start<data.length; start+=8192) binary += String.fromCharCode(...data.subarray(start,start+8192));
      image.src = checkImage('data:'+section.dataset.document+';base64,'+btoa(binary));
      document.documentElement.dataset.reportStage = 'decode-image';
      await image.decode();
      const figure = document.createElement('figure'); figure.className = 'document-page';
      const caption = document.createElement('figcaption'); caption.textContent = documentCaption(section,1,1);
      figure.append(caption,image); container.append(figure);
    }
  }
  document.documentElement.dataset.reportStage = 'fonts';
  await document.fonts.ready;
  document.documentElement.dataset.reportStage = 'images';
  await Promise.all([...document.images].map(image => image.decode()));
  document.documentElement.dataset.reportReady = 'yes';
  status.textContent = status.dataset.ready; button.disabled = false;
}
prepare().catch(error => {
  // Fixed diagnostic name only; never log document contents or patient text.
  document.documentElement.dataset.reportError = error.name;
  status.textContent = status.dataset.error; status.setAttribute('role','alert');
});

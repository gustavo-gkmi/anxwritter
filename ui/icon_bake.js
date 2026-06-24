// icon_bake.js — client-side custom-icon baking (no Pillow, no server).
//
// Mirrors anxwritter/custom_icons.py:convert_to_bmp so the browser produces the
// same conditioned image the library would: downscale-only to <=128px, pad to a
// square with magenta, hard 1-bit alpha threshold, composite onto magenta
// (255,0,255 = ANB's transparent key), emit a full 24-bit BMP. The result is a
// `data:image/bmp;base64,...` URI — already "baked", so it passes the library's
// config Pillow gate. zlib compression is left to the library at build time, so
// no JS zlib dependency is needed here.

(function () {
  const MAX_SIZE = 128;
  const MAGENTA = [255, 0, 255];

  // RGB square (Uint8Array, row-major top-down) -> 24-bit BMP data: URI.
  function rgbSquareToBmpDataUri(rgb, w, h) {
    const rowSize = (w * 3 + 3) & ~3;            // rows padded to 4 bytes
    const pixSize = rowSize * h;
    const fileSize = 54 + pixSize;
    const buf = new Uint8Array(fileSize);
    const dv = new DataView(buf.buffer);
    buf[0] = 0x42; buf[1] = 0x4d;                // 'BM'
    dv.setUint32(2, fileSize, true);
    dv.setUint32(10, 54, true);                  // pixel data offset
    dv.setUint32(14, 40, true);                  // BITMAPINFOHEADER size
    dv.setInt32(18, w, true);
    dv.setInt32(22, h, true);                    // positive => bottom-up rows
    dv.setUint16(26, 1, true);                   // planes
    dv.setUint16(28, 24, true);                  // bpp
    dv.setUint32(34, pixSize, true);
    dv.setInt32(38, 2835, true);                 // ~72 DPI
    dv.setInt32(42, 2835, true);
    let p = 54;
    for (let y = h - 1; y >= 0; y--) {           // bottom-up
      const rowStart = p;
      for (let x = 0; x < w; x++) {
        const si = (y * w + x) * 3;
        buf[p++] = rgb[si + 2];                  // B
        buf[p++] = rgb[si + 1];                  // G
        buf[p++] = rgb[si];                      // R
      }
      while (p - rowStart < rowSize) buf[p++] = 0;
    }
    let bin = '';
    for (let i = 0; i < buf.length; i++) bin += String.fromCharCode(buf[i]);
    return 'data:image/bmp;base64,' + btoa(bin);
  }

  // HTMLImageElement (loaded) -> baked BMP data: URI.
  function bakeImageElement(img) {
    let w = img.naturalWidth, h = img.naturalHeight;
    if (!w || !h) throw new Error('image has zero size');
    const scale = Math.min(1, MAX_SIZE / Math.max(w, h));  // downscale only
    const dw = Math.max(1, Math.round(w * scale));
    const dh = Math.max(1, Math.round(h * scale));
    const canvas = document.createElement('canvas');
    canvas.width = dw; canvas.height = dh;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, dw, dh);
    ctx.drawImage(img, 0, 0, dw, dh);
    const data = ctx.getImageData(0, 0, dw, dh).data;

    const side = Math.max(dw, dh);
    const offx = Math.floor((side - dw) / 2);
    const offy = Math.floor((side - dh) / 2);
    const rgb = new Uint8Array(side * side * 3);
    for (let i = 0; i < rgb.length; i += 3) {              // magenta fill
      rgb[i] = MAGENTA[0]; rgb[i + 1] = MAGENTA[1]; rgb[i + 2] = MAGENTA[2];
    }
    for (let y = 0; y < dh; y++) {
      for (let x = 0; x < dw; x++) {
        const si = (y * dw + x) * 4;
        if (data[si + 3] >= 128) {                         // 1-bit alpha threshold
          const di = ((y + offy) * side + (x + offx)) * 3;
          rgb[di] = data[si]; rgb[di + 1] = data[si + 1]; rgb[di + 2] = data[si + 2];
        }
      }
    }
    return rgbSquareToBmpDataUri(rgb, side, side);
  }

  // File/Blob -> Promise<baked BMP data: URI>. A file that is already a BMP is
  // still re-baked through the canvas (re-encodes to a clean 24-bit square).
  function bakeFile(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () => reject(new Error('could not read file'));
      reader.onload = () => {
        const img = new Image();
        img.onload = () => {
          try { resolve(bakeImageElement(img)); }
          catch (e) { reject(e); }
        };
        img.onerror = () => reject(new Error('not a decodable image'));
        img.src = reader.result;
      };
      reader.readAsDataURL(file);
    });
  }

  window.IconBake = { bakeFile, bakeImageElement };
})();

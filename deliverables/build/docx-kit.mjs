import { esc, XML_HEADER, makeZip } from './ooxml.mjs';

export const CONTENT_TWIPS = 9638;
export const FONT_HEAD = '\u5fae\u8f6f\u96c5\u9ed1';
export const FONT_EA = '\u5b8b\u4f53';
export const FONT_LATIN = 'Calibri';
export const FONT_MONO = 'Consolas';
export const C_HEADING = '123A6B';
export const C_HEAD2 = '1F4E79';
export const C_BODY = '1B2733';
export const C_MUTED = '5B6B7C';
export const C_ACCENT = '2E86DE';

const NS_W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main';

const GLOB_GUARD = '\u0001';

function parseInline(value) {
  const text = String(value).split('/**').join('/' + GLOB_GUARD + GLOB_GUARD);
  const nodes = [];
  const re = /\*\*(.+?)\*\*|`([^`]+)`/g;
  let last = 0;
  let match = re.exec(text);
  while (match) {
    if (match.index > last) nodes.push({ text: text.slice(last, match.index) });
    if (match[1] !== undefined) nodes.push({ text: match[1], bold: true });
    else nodes.push({ text: match[2], mono: true });
    last = re.lastIndex;
    match = re.exec(text);
  }
  if (last < text.length) nodes.push({ text: text.slice(last) });
  return nodes
    .map((node) => ({ ...node, text: node.text.split(GLOB_GUARD).join('*') }))
    .filter((node) => node.text !== '');
}

function runXml(node, base) {
  const opts = base || {};
  const size = opts.size || 21;
  const latin = node.mono ? FONT_MONO : opts.latin || FONT_LATIN;
  const ea = node.mono ? FONT_MONO : opts.ea || FONT_EA;
  const out = ['<w:r><w:rPr>'];
  out.push(`<w:rFonts w:ascii="${latin}" w:hAnsi="${latin}" w:eastAsia="${ea}" w:cs="${latin}"/>`);
  if (node.bold || opts.bold) out.push('<w:b/><w:bCs/>');
  if (opts.italic) out.push('<w:i/><w:iCs/>');
  if (opts.color) out.push(`<w:color w:val="${opts.color}"/>`);
  out.push(`<w:sz w:val="${size}"/><w:szCs w:val="${size}"/></w:rPr>`);
  out.push(`<w:t xml:space="preserve">${esc(node.text)}</w:t></w:r>`);
  return out.join('');
}

export function run(text, opts) {
  return parseInline(String(text)).map((node) => runXml(node, opts)).join('');
}

/** Internal jump target for a bookmark created by para({ bookmark }). */
export function link(text, anchor, opts) {
  return `<w:hyperlink w:anchor="${anchor}">${run(text, opts)}</w:hyperlink>`;
}

export function para(text, opts) {
  const o = opts || {};
  const head = [];
  if (o.style) head.push(`<w:pStyle w:val="${o.style}"/>`);
  if (o.keepNext) head.push('<w:keepNext/>');
  if (o.fill) head.push(`<w:shd w:val="clear" w:color="auto" w:fill="${o.fill}"/>`);
  head.push(`<w:spacing w:before="${o.before ?? 0}" w:after="${o.after ?? 130}" w:line="${o.line ?? 300}" w:lineRule="auto"/>`);
  if (o.indent || o.hanging) head.push(`<w:ind w:left="${o.indent || 0}" w:hanging="${o.hanging || 0}"/>`);
  head.push(`<w:jc w:val="${o.align || 'both'}"/>`);
  if (o.outline !== undefined) head.push(`<w:outlineLvl w:val="${o.outline}"/>`);
  const body = o.rich || run(text, o.run || {});
  const mark = o.bookmark ? `<w:bookmarkStart w:id="${o.bookmarkId || 1}" w:name="${o.bookmark}"/>` : '';
  const markEnd = o.bookmark ? `<w:bookmarkEnd w:id="${o.bookmarkId || 1}"/>` : '';
  return `<w:p><w:pPr>${head.join('')}</w:pPr>${mark}${body}${markEnd}</w:p>`;
}

export function bullet(text, opts) {
  const o = opts || {};
  const size = o.size || 21;
  const marker = o.marker || '\u2022  ';
  const rich = `<w:r><w:rPr><w:rFonts w:ascii="${FONT_LATIN}" w:hAnsi="${FONT_LATIN}" w:eastAsia="${FONT_EA}"/><w:color w:val="${C_ACCENT}"/><w:sz w:val="${size}"/><w:szCs w:val="${size}"/></w:rPr><w:t xml:space="preserve">${esc(marker)}</w:t></w:r>`
    + run(text, { size, ...(o.run || {}) });
  return para('', { before: 0, after: 70, line: 290, indent: 360, hanging: 360, rich });
}

function cellXml(text, width, opts) {
  const o = opts || {};
  const fill = o.fill ? `<w:shd w:val="clear" w:color="auto" w:fill="${o.fill}"/>` : '';
  const lines = Array.isArray(text) ? text : String(text).split('\n');
  const paras = lines.map((line) => para(line, {
    after: 40,
    before: 40,
    line: 260,
    align: o.align || 'left',
    run: { size: o.size || 19, bold: o.bold, color: o.color || C_BODY, ea: o.ea },
  })).join('');
  return `<w:tc><w:tcPr><w:tcW w:w="${width}" w:type="dxa"/>${fill}<w:vAlign w:val="${o.valign || 'center'}"/></w:tcPr>${paras}</w:tc>`;
}

export function table(spec) {
  const widths = spec.widths;
  const total = widths.reduce((sum, value) => sum + value, 0);
  const cols = widths.map((value) => Math.round((value / total) * CONTENT_TWIPS));
  const size = spec.size || 19;
  const headFill = spec.headerFill || 'DCE6F1';
  const zebra = spec.zebraFill || null;
  const rows = [];

  if (spec.header) {
    const cells = spec.header.map((text, index) => cellXml(text, cols[index], {
      fill: headFill, bold: true, color: C_HEADING, size, align: spec.headerAlign || 'left',
    })).join('');
    rows.push(`<w:tr><w:trPr><w:tblHeader/></w:trPr>${cells}</w:tr>`);
  }

  spec.rows.forEach((row, rowIndex) => {
    const fill = zebra && rowIndex % 2 === 1 ? zebra : null;
    const cells = row.map((text, index) => cellXml(text, cols[index], {
      fill, size, bold: spec.boldFirstColumn && index === 0,
      align: (spec.aligns && spec.aligns[index]) || 'left',
    })).join('');
    rows.push(`<w:tr>${cells}</w:tr>`);
  });

  const borders = ['top', 'left', 'bottom', 'right', 'insideH', 'insideV']
    .map((side) => `<w:${side} w:val="single" w:sz="6" w:space="0" w:color="B9C6D8"/>`).join('');

  return `<w:tbl><w:tblPr><w:tblW w:w="${CONTENT_TWIPS}" w:type="dxa"/><w:jc w:val="center"/><w:tblBorders>${borders}</w:tblBorders><w:tblLayout w:type="fixed"/><w:tblCellMar><w:top w:w="68" w:type="dxa"/><w:left w:w="96" w:type="dxa"/><w:bottom w:w="68" w:type="dxa"/><w:right w:w="96" w:type="dxa"/></w:tblCellMar><w:tblLook w:val="04A0" w:firstRow="1" w:lastRow="0" w:firstColumn="0" w:lastColumn="0" w:noHBand="0" w:noVBand="1"/></w:tblPr>`
    + `<w:tblGrid>${cols.map((value) => `<w:gridCol w:w="${value}"/>`).join('')}</w:tblGrid>${rows.join('')}</w:tbl>`;
}

export function callout(title, lines, fill) {
  const bg = fill || 'EEF4FB';
  const paras = [];
  if (title) paras.push(para(title, { after: 60, line: 280, run: { size: 21, bold: true, color: C_HEADING } }));
  for (const line of lines) paras.push(bullet(line, { after: 40 }));
  const border = ['top', 'left', 'bottom', 'right']
    .map((side) => `<w:${side} w:val="single" w:sz="6" w:space="0" w:color="C7D8EC"/>`).join('');
  return `<w:tbl><w:tblPr><w:tblW w:w="${CONTENT_TWIPS}" w:type="dxa"/><w:jc w:val="center"/><w:tblBorders>${border}</w:tblBorders><w:tblLayout w:type="fixed"/><w:tblCellMar><w:top w:w="120" w:type="dxa"/><w:left w:w="160" w:type="dxa"/><w:bottom w:w="120" w:type="dxa"/><w:right w:w="160" w:type="dxa"/></w:tblCellMar></w:tblPr><w:tblGrid><w:gridCol w:w="${CONTENT_TWIPS}"/></w:tblGrid>`
    + `<w:tr><w:tc><w:tcPr><w:tcW w:w="${CONTENT_TWIPS}" w:type="dxa"/><w:shd w:val="clear" w:color="auto" w:fill="${bg}"/></w:tcPr>${paras.join('')}</w:tc></w:tr></w:tbl>`;
}

export function codeBlock(lines, caption) {
  const body = lines.map((line) => para(line, {
    after: 0, before: 0, line: 250, align: 'left',
    rich: run(line, { size: 17, latin: FONT_MONO, ea: FONT_MONO, color: '27445F' }),
  }));
  if (caption) body.push(para(caption, { after: 0, before: 80, line: 260, align: 'left', run: { size: 18, color: C_MUTED } }));
  const border = ['top', 'left', 'bottom', 'right']
    .map((side) => `<w:${side} w:val="single" w:sz="6" w:space="0" w:color="D3DCE6"/>`).join('');
  return `<w:tbl><w:tblPr><w:tblW w:w="${CONTENT_TWIPS}" w:type="dxa"/><w:jc w:val="center"/><w:tblBorders>${border}</w:tblBorders><w:tblLayout w:type="fixed"/><w:tblCellMar><w:top w:w="120" w:type="dxa"/><w:left w:w="160" w:type="dxa"/><w:bottom w:w="120" w:type="dxa"/><w:right w:w="160" w:type="dxa"/></w:tblCellMar></w:tblPr><w:tblGrid><w:gridCol w:w="${CONTENT_TWIPS}"/></w:tblGrid>`
    + `<w:tr><w:tc><w:tcPr><w:tcW w:w="${CONTENT_TWIPS}" w:type="dxa"/><w:shd w:val="clear" w:color="auto" w:fill="F5F7FA"/></w:tcPr>${body.join('')}</w:tc></w:tr></w:tbl>`;
}

export function spacer(twips) {
  return para('', { after: twips || 120, line: 240 });
}

export function pageBreak() {
  return `<w:p><w:pPr><w:spacing w:before="0" w:after="0"/></w:pPr><w:r><w:br w:type="page"/></w:r></w:p>`;
}

const STYLES = `${XML_HEADER}<w:styles xmlns:w="${NS_W}"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="${FONT_LATIN}" w:hAnsi="${FONT_LATIN}" w:eastAsia="${FONT_EA}" w:cs="${FONT_LATIN}"/><w:color w:val="${C_BODY}"/><w:sz w:val="21"/><w:szCs w:val="21"/><w:lang w:val="en-US" w:eastAsia="zh-CN" w:bidi="ar-SA"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="130" w:line="300" w:lineRule="auto"/><w:jc w:val="both"/></w:pPr></w:pPrDefault></w:docDefaults>`
+ `<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>`
+ `<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:spacing w:before="0" w:after="200" w:line="340" w:lineRule="auto"/><w:jc w:val="center"/></w:pPr><w:rPr><w:rFonts w:ascii="${FONT_HEAD}" w:hAnsi="${FONT_HEAD}" w:eastAsia="${FONT_HEAD}"/><w:b/><w:color w:val="000000"/><w:sz w:val="46"/><w:szCs w:val="46"/></w:rPr></w:style>`
+ `<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:pBdr><w:bottom w:val="single" w:sz="8" w:space="4" w:color="C7D5E8"/></w:pBdr><w:spacing w:before="360" w:after="180" w:line="300" w:lineRule="auto"/><w:jc w:val="left"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:rFonts w:ascii="${FONT_HEAD}" w:hAnsi="${FONT_HEAD}" w:eastAsia="${FONT_HEAD}"/><w:b/><w:color w:val="${C_HEADING}"/><w:sz w:val="32"/><w:szCs w:val="32"/></w:rPr></w:style>`
+ `<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:spacing w:before="260" w:after="130" w:line="300" w:lineRule="auto"/><w:jc w:val="left"/><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:rFonts w:ascii="${FONT_HEAD}" w:hAnsi="${FONT_HEAD}" w:eastAsia="${FONT_HEAD}"/><w:b/><w:color w:val="${C_HEAD2}"/><w:sz w:val="26"/><w:szCs w:val="26"/></w:rPr></w:style>`
+ `<w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:spacing w:before="200" w:after="100" w:line="300" w:lineRule="auto"/><w:jc w:val="left"/><w:outlineLvl w:val="2"/></w:pPr><w:rPr><w:rFonts w:ascii="${FONT_HEAD}" w:hAnsi="${FONT_HEAD}" w:eastAsia="${FONT_HEAD}"/><w:b/><w:color w:val="${C_BODY}"/><w:sz w:val="22"/><w:szCs w:val="22"/></w:rPr></w:style>`
+ `</w:styles>`;

const SETTINGS = `${XML_HEADER}<w:settings xmlns:w="${NS_W}"><w:zoom w:percent="100"/><w:defaultTabStop w:val="420"/><w:characterSpacingControl w:val="compressPunctuation"/><w:compat><w:compatSetting w:name="compatibilityMode" w:uri="http://schemas.microsoft.com/office/word" w:val="15"/></w:compat></w:settings>`;

const SECT_PR = '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1418" w:right="1134" w:bottom="1418" w:left="1134" w:header="851" w:footer="992" w:gutter="0"/><w:docGrid w:linePitch="312"/></w:sectPr>';

export function buildDocx(options) {
  const body = options.blocks.join('') + '<w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr></w:p>' + SECT_PR;
  const documentXml = `${XML_HEADER}<w:document xmlns:w="${NS_W}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><w:body>${body}</w:body></w:document>`;
  const contentTypes = `${XML_HEADER}<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/><Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/><Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/></Types>`;
  const rootRels = `${XML_HEADER}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/></Relationships>`;
  const docRels = `${XML_HEADER}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/></Relationships>`;
  const core = `${XML_HEADER}<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>${esc(options.title)}</dc:title><dc:subject>${esc(options.subject || '')}</dc:subject><dc:creator>${esc(options.author || '')}</dc:creator><cp:lastModifiedBy>${esc(options.author || '')}</cp:lastModifiedBy><dcterms:created xsi:type="dcterms:W3CDTF">2026-09-20T09:00:00Z</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">2026-09-20T09:00:00Z</dcterms:modified></cp:coreProperties>`;
  const app = `${XML_HEADER}<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>Microsoft Office Word</Application><DocSecurity>0</DocSecurity><ScaleCrop>false</ScaleCrop><Company></Company><SharedDoc>false</SharedDoc><HyperlinksChanged>false</HyperlinksChanged><AppVersion>16.0000</AppVersion></Properties>`;

  return makeZip([
    { name: '[Content_Types].xml', data: contentTypes },
    { name: '_rels/.rels', data: rootRels },
    { name: 'docProps/core.xml', data: core },
    { name: 'docProps/app.xml', data: app },
    { name: 'word/document.xml', data: documentXml },
    { name: 'word/_rels/document.xml.rels', data: docRels },
    { name: 'word/styles.xml', data: STYLES },
    { name: 'word/settings.xml', data: SETTINGS },
  ]);
}

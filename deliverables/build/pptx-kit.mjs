import { esc, XML_HEADER, makeZip } from './ooxml.mjs';

export const SLIDE_W = 12192000;
export const SLIDE_H = 6858000;

export const INK = '1B2733';
export const NAVY = '123A6B';
export const BLUE = '1F4E79';
export const ACCENT = '2E86DE';
export const AMBER = 'C8873C';
export const GREEN = '1E8449';
export const MUTED = '5B6B7C';
export const LIGHT = 'EEF4FB';
export const LINE = 'C7D5E8';
export const WC = '\u5fae\u8f6f\u96c5\u9ed1';
export const LA = 'Segoe UI';

const NS = 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"';

export function inch(value) {
  return Math.round(value * 914400);
}

export function pt(value) {
  return Math.round(value * 12700);
}

const GLOB_GUARD = '\u0001';

function parseInline(value) {
  const text = String(value).split('/**').join('/' + GLOB_GUARD + GLOB_GUARD);
  const nodes = [];
  const re = /\*\*(.+?)\*\*/g;
  let last = 0;
  let match = re.exec(text);
  while (match) {
    if (match.index > last) nodes.push({ text: text.slice(last, match.index) });
    nodes.push({ text: match[1], bold: true });
    last = re.lastIndex;
    match = re.exec(text);
  }
  if (last < text.length) nodes.push({ text: text.slice(last) });
  return nodes
    .map((node) => ({ ...node, text: node.text.split(GLOB_GUARD).join('*') }))
    .filter((node) => node.text !== '');
}

function runXml(node, base) {
  const size = node.size || base.size || 1600;
  const color = node.color || base.color || INK;
  const bold = node.bold || base.bold;
  const attrs = ['lang="zh-CN"', 'altLang="en-US"', `sz="${size}"`];
  if (bold) attrs.push('b="1"');
  if (base.italic) attrs.push('i="1"');
  attrs.push('dirty="0"');
  const font = node.mono ? 'Consolas' : LA;
  const ea = node.mono ? 'Consolas' : WC;
  return `<a:r><a:rPr ${attrs.join(' ')}><a:solidFill><a:srgbClr val="${color}"/></a:solidFill><a:latin typeface="${font}"/><a:ea typeface="${ea}"/><a:cs typeface="${font}"/></a:rPr><a:t>${esc(node.text)}</a:t></a:r>`;
}

export function P(text, options) {
  const o = options || {};
  const attrs = [`marL="${o.marL ?? 0}"`, `indent="${o.indent ?? 0}"`];
  if (o.align) attrs.push(`algn="${o.align}"`);
  const children = [];
  if (o.lineSpacingPct) children.push(`<a:lnSpc><a:spcPct val="${o.lineSpacingPct}"/></a:lnSpc>`);
  if (o.before !== undefined) children.push(`<a:spcBef><a:spcPts val="${o.before}"/></a:spcBef>`);
  if (o.after !== undefined) children.push(`<a:spcAft><a:spcPts val="${o.after}"/></a:spcAft>`);
  if (o.bullet) {
    children.push(`<a:buClr><a:srgbClr val="${o.bulletColor || ACCENT}"/></a:buClr><a:buFont typeface="Arial"/><a:buChar char="${o.bulletChar || '\u2022'}"/>`);
  } else {
    children.push('<a:buNone/>');
  }
  const runs = [];
  if (Array.isArray(text)) {
    for (const seg of text) runs.push(runXml(seg, o));
  } else {
    for (const node of parseInline(text)) runs.push(runXml(node, o));
  }
  return `<a:p><a:pPr ${attrs.join(' ')}>${children.join('')}</a:pPr>${runs.join('')}</a:p>`;
}

function shapeBase(id, name) {
  return `<p:nvSpPr><p:cNvPr id="${id}" name="${esc(name)}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>`;
}

export function box(spec) {
  const prst = spec.prst || 'rect';
  const avLst = prst === 'roundRect' ? `<a:avLst><a:gd name="adj" fmla="val ${spec.radius ?? 8000}"/></a:avLst>` : '<a:avLst/>';
  const fill = spec.fill ? `<a:solidFill><a:srgbClr val="${spec.fill}"/></a:solidFill>` : '<a:noFill/>';
  const line = spec.line
    ? `<a:ln w="${spec.lineWidth || 9525}"><a:solidFill><a:srgbClr val="${spec.line}"/></a:solidFill></a:ln>`
    : '<a:ln><a:noFill/></a:ln>';
  const body = spec.paras
    ? `<p:txBody><a:bodyPr wrap="square" lIns="${spec.padX ?? 0}" tIns="${spec.padY ?? 0}" rIns="${spec.padX ?? 0}" bIns="${spec.padY ?? 0}" anchor="${spec.anchor || 't'}"><a:normAutofit/></a:bodyPr><a:lstStyle/>${spec.paras.join('')}</p:txBody>`
    : '';
  return `<p:sp>${shapeBase(spec.id, spec.name)}<p:spPr><a:xfrm><a:off x="${spec.x}" y="${spec.y}"/><a:ext cx="${spec.w}" cy="${spec.h}"/></a:xfrm><a:prstGeom prst="${prst}">${avLst}</a:prstGeom>${fill}${line}</p:spPr>${body}</p:sp>`;
}

export function textBox(spec) {
  return box({ ...spec, padX: spec.padX ?? 0, padY: spec.padY ?? 0 });
}

function lineXml(tag, color) {
  return `<a:${tag} w="9525" cap="flat" cmpd="sng" algn="ctr"><a:solidFill><a:srgbClr val="${color}"/></a:solidFill><a:prstDash val="solid"/></a:${tag}>`;
}

function cellXml(text, options) {
  const o = options || {};
  const fill = o.fill ? `<a:solidFill><a:srgbClr val="${o.fill}"/></a:solidFill>` : '<a:noFill/>';
  const mine = ['lnL', 'lnR', 'lnT', 'lnB'].map((tag) => lineXml(tag, o.border || LINE)).join('');
  const lines = Array.isArray(text) ? text : String(text).split('\n');
  const paras = lines.map((line) => P(line, {
    size: o.size || 1200,
    bold: o.bold,
    color: o.color || INK,
    align: o.align || 'l',
    after: 0,
    before: 0,
    lineSpacingPct: 90000,
  })).join('');
  return `<a:tc><a:txBody><a:bodyPr lIns="0" tIns="0" rIns="0" bIns="0"/><a:lstStyle/>${paras}</a:txBody>`
    + `<a:tcPr marL="108000" marR="108000" marT="54000" marB="54000" anchor="${o.anchor || 'ctr'}">${mine}${fill}</a:tcPr></a:tc>`;
}

export function tableFrame(spec) {
  const total = spec.colW.reduce((sum, value) => sum + value, 0);
  const cols = spec.colW.map((value) => Math.round((value / total) * spec.w));
  const totalH = spec.h || ((spec.header ? spec.rowH : 0) + spec.rows.length * (spec.bodyH || spec.rowH));
  const rows = [];
  if (spec.header) {
    rows.push(`<a:tr h="${spec.rowH}">${spec.header.map((text) => cellXml(text, {
      fill: spec.headerFill || NAVY, color: 'FFFFFF', bold: true, size: spec.size || 1200, align: spec.headerAlign || 'l',
    })).join('')}</a:tr>`);
  }
  spec.rows.forEach((row, rowIndex) => {
    rows.push(`<a:tr h="${spec.bodyH || spec.rowH}">${row.map((text, index) => cellXml(text, {
      fill: spec.zebra !== false && rowIndex % 2 === 1 ? (spec.zebraFill || LIGHT) : 'FFFFFF',
      size: spec.size || 1200,
      bold: spec.boldFirst && index === 0,
      color: spec.boldFirst && index === 0 ? BLUE : INK,
      align: (spec.aligns && spec.aligns[index]) || 'l',
    })).join('')}</a:tr>`);
  });
  return `<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="${spec.id}" name="${esc(spec.name || 'Table')}"/><p:cNvGraphicFramePr><a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr><p:nvPr/></p:nvGraphicFramePr>`
    + `<p:xfrm><a:off x="${spec.x}" y="${spec.y}"/><a:ext cx="${spec.w}" cy="${totalH}"/></p:xfrm>`
    + `<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table"><a:tbl><a:tblPr firstRow="1" bandRow="0"/><a:tblGrid>${cols.map((value) => `<a:gridCol w="${value}"/>`).join('')}</a:tblGrid>${rows.join('')}</a:tbl></a:graphicData></a:graphic></p:graphicFrame>`;
}

export function slideXml(shapes, background) {
  const bg = `<p:bg><p:bgPr><a:solidFill><a:srgbClr val="${background || 'FFFFFF'}"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>`;
  const tree = `<p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>${shapes.join('')}</p:spTree>`;
  return `${XML_HEADER}<p:sld ${NS}><p:cSld>${bg}${tree}</p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>`;
}
const THEME = `${XML_HEADER}<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="TrainSystem"><a:themeElements>`
  + `<a:clrScheme name="TrainSystem"><a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1><a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1><a:dk2><a:srgbClr val="44546A"/></a:dk2><a:lt2><a:srgbClr val="E7E6E6"/></a:lt2><a:accent1><a:srgbClr val="${ACCENT}"/></a:accent1><a:accent2><a:srgbClr val="${NAVY}"/></a:accent2><a:accent3><a:srgbClr val="${AMBER}"/></a:accent3><a:accent4><a:srgbClr val="${GREEN}"/></a:accent4><a:accent5><a:srgbClr val="8E6FD1"/></a:accent5><a:accent6><a:srgbClr val="E74C3C"/></a:accent6><a:hlink><a:srgbClr val="0563C1"/></a:hlink><a:folHlink><a:srgbClr val="954F72"/></a:folHlink></a:clrScheme>`
  + `<a:fontScheme name="TrainSystem"><a:majorFont><a:latin typeface="${LA}"/><a:ea typeface="${WC}"/><a:cs typeface=""/></a:majorFont><a:minorFont><a:latin typeface="${LA}"/><a:ea typeface="${WC}"/><a:cs typeface=""/></a:minorFont></a:fontScheme>`
  + `<a:fmtScheme name="TrainSystem"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst>`
  + `<a:lnStyleLst><a:ln w="6350" cap="flat" cmpd="sng" algn="ctr"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:prstDash val="solid"/></a:ln><a:ln w="12700" cap="flat" cmpd="sng" algn="ctr"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:prstDash val="solid"/></a:ln><a:ln w="19050" cap="flat" cmpd="sng" algn="ctr"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:prstDash val="solid"/></a:ln></a:lnStyleLst>`
  + `<a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst>`
  + `<a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst></a:fmtScheme></a:themeElements><a:objectDefaults/><a:extraClrSchemeLst/></a:theme>`;

const EMPTY_TREE = '<p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree>';

const SLIDE_MASTER = `${XML_HEADER}<p:sldMaster ${NS}><p:cSld><p:bg><p:bgPr><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>${EMPTY_TREE}</p:cSld>`
  + `<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>`
  + `<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>`
  + `<p:txStyles><p:titleStyle><lvl1pPr algn="l"><a:defRPr sz="2800" b="1"><a:solidFill><a:srgbClr val="${NAVY}"/></a:solidFill><a:latin typeface="${LA}"/><a:ea typeface="${WC}"/></a:defRPr></lvl1pPr></p:titleStyle>`
  + `<p:bodyStyle>${[1, 2, 3, 4, 5].map((level) => `<lvl${level}pPr marL="${(level - 1) * 228600}" indent="-228600"><a:defRPr sz="${1800 - (level - 1) * 100}"><a:solidFill><a:srgbClr val="${INK}"/></a:solidFill><a:latin typeface="${LA}"/><a:ea typeface="${WC}"/></a:defRPr></lvl${level}pPr>`).join('')}</p:bodyStyle>`
  + `<p:otherStyle><lvl1pPr><a:defRPr sz="1200"><a:latin typeface="${LA}"/><a:ea typeface="${WC}"/></a:defRPr></lvl1pPr></p:otherStyle></p:txStyles></p:sldMaster>`;

const SLIDE_LAYOUT = `${XML_HEADER}<p:sldLayout ${NS} type="blank" preserve="1"><p:cSld name="\u7a7a\u767d">${EMPTY_TREE}</p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>`;

const EMPTY_RELS = `${XML_HEADER}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"></Relationships>`;

export function buildPptx(options) {
  const slides = options.slides;
  const entries = [];
  const slideOverrides = slides.map((_, index) => `<Override PartName="/ppt/slides/slide${index + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>`).join('');
  const contentTypes = `${XML_HEADER}<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>`
    + `<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>`
    + `<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>`
    + `<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>`
    + `<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>`
    + `<Override PartName="/ppt/presProps.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presProps+xml"/>`
    + slideOverrides
    + `<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/><Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/></Types>`;

  const slideIds = slides.map((_, index) => `<p:sldId id="${256 + index}" r:id="rId${index + 2}"/>`).join('');
  const presentation = `${XML_HEADER}<p:presentation ${NS} saveSubsetFonts="1" autoCompressPictures="0"><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst><p:sldIdLst>${slideIds}</p:sldIdLst><p:sldSz cx="${SLIDE_W}" cy="${SLIDE_H}"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>`;

  const presRels = `${XML_HEADER}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>`
    + slides.map((_, index) => `<Relationship Id="rId${index + 2}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide${index + 1}.xml"/>`).join('')
    + `<Relationship Id="rId${slides.length + 2}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/presProps" Target="presProps.xml"/><Relationship Id="rId${slides.length + 3}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/></Relationships>`;

  const masterRels = `${XML_HEADER}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/></Relationships>`;
  const layoutRels = `${XML_HEADER}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/></Relationships>`;

  const rootRels = `${XML_HEADER}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/></Relationships>`;

  const core = `${XML_HEADER}<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>${esc(options.title)}</dc:title><dc:creator>${esc(options.author || '')}</dc:creator><cp:lastModifiedBy>${esc(options.author || '')}</cp:lastModifiedBy><dcterms:created xsi:type="dcterms:W3CDTF">2026-09-20T09:00:00Z</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">2026-09-20T09:00:00Z</dcterms:modified></cp:coreProperties>`;
  const app = `${XML_HEADER}<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>Microsoft Office PowerPoint</Application><PresentationFormat>\u5bbd\u5c4f</PresentationFormat><Slides>${slides.length}</Slides><Notes>0</Notes><HiddenSlides>0</HiddenSlides><Company></Company><AppVersion>16.0000</AppVersion></Properties>`;
  const presProps = `${XML_HEADER}<p:presentationPr ${NS}><p:extLst/></p:presentationPr>`;

  entries.push({ name: '[Content_Types].xml', data: contentTypes });
  entries.push({ name: '_rels/.rels', data: rootRels });
  entries.push({ name: 'docProps/core.xml', data: core });
  entries.push({ name: 'docProps/app.xml', data: app });
  entries.push({ name: 'ppt/presentation.xml', data: presentation });
  entries.push({ name: 'ppt/_rels/presentation.xml.rels', data: presRels });
  entries.push({ name: 'ppt/presProps.xml', data: presProps });
  entries.push({ name: 'ppt/theme/theme1.xml', data: THEME });
  entries.push({ name: 'ppt/slideMasters/slideMaster1.xml', data: SLIDE_MASTER });
  entries.push({ name: 'ppt/slideMasters/_rels/slideMaster1.xml.rels', data: masterRels });
  entries.push({ name: 'ppt/slideLayouts/slideLayout1.xml', data: SLIDE_LAYOUT });
  entries.push({ name: 'ppt/slideLayouts/_rels/slideLayout1.xml.rels', data: layoutRels });
  slides.forEach((slide, index) => {
    entries.push({ name: `ppt/slides/slide${index + 1}.xml`, data: slideXml(slide.shapes, slide.background) });
    entries.push({ name: `ppt/slides/_rels/slide${index + 1}.xml.rels`, data: EMPTY_RELS });
  });

  return makeZip(entries);
}
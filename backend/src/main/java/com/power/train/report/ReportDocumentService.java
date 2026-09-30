package com.power.train.report;

import com.power.train.report.ReportTemplate.DocSection;
import com.power.train.report.ReportTemplate.Row;
import com.power.train.support.Texts;
import java.io.ByteArrayOutputStream;
import java.io.Closeable;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import org.apache.fontbox.ttf.TrueTypeCollection;
import org.apache.fontbox.ttf.TrueTypeFont;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDPageContentStream;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDType0Font;
import org.apache.poi.xwpf.usermodel.ParagraphAlignment;
import org.apache.poi.xwpf.usermodel.XWPFDocument;
import org.apache.poi.xwpf.usermodel.XWPFParagraph;
import org.apache.poi.xwpf.usermodel.XWPFRun;
import org.apache.poi.xwpf.usermodel.XWPFTable;
import org.apache.poi.xwpf.usermodel.XWPFTable.XWPFBorderType;
import org.apache.poi.xwpf.usermodel.XWPFTableCell;
import org.apache.poi.xwpf.usermodel.XWPFTableRow;
import org.openxmlformats.schemas.wordprocessingml.x2006.main.CTFonts;
import org.openxmlformats.schemas.wordprocessingml.x2006.main.CTRPr;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

/**
 * 按“规定框格”渲染报告文档：同一套 DocSection 模型分别输出 PDF（PDFBox，内嵌中文字体）
 * 与 Word（POI XWPF），并把文档正文抽取为纯文本供 AI Agent 读取。
 */
@Service
public class ReportDocumentService {

    private static final Logger log = LoggerFactory.getLogger(ReportDocumentService.class);

    private static final DateTimeFormatter STAMP = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm");
    private static final float PAGE_WIDTH = PDRectangle.A4.getWidth();
    private static final float PAGE_HEIGHT = PDRectangle.A4.getHeight();
    private static final float MARGIN = 46f;
    private static final float LABEL_WIDTH = 96f;
    private static final float BOTTOM_LIMIT = 74f;
    private static final float SIGNATURE_HEIGHT = 52f;
    private static final String FOOTER_NOTE = "本报告由系统按“实操任务检测报告”模板框格自动生成，加盖签字后方可归档";

    /** 标题字体候选：本机 Windows 字体 → 容器内 CJK 字体 → 字体集合(.ttc)。 */
    private static final List<String> TITLE_FONT_NAMES = List.of(
        "simhei.ttf", "msyh.ttc", "simsun.ttc",
        "NotoSansCJK-Bold.ttc", "NotoSansCJK-Regular.ttc", "NotoSansSC-Regular.otf",
        "wqy-zenhei.ttc", "DroidSansFallbackFull.ttf");
    /** 正文字体候选：TTF/OTF 的 ToUnicode 映射干净，优先于 .ttc。 */
    private static final List<String> BODY_FONT_NAMES = List.of(
        "simkai.ttf", "simsun.ttc", "msyh.ttc",
        "NotoSansCJK-Regular.ttc", "NotoSansSC-Regular.otf",
        "wqy-zenhei.ttc", "wqy-microhei.ttc", "DroidSansFallbackFull.ttf");
    /** 打进 jar 的兜底字体，文件不存在时自动跳过。 */
    private static final List<String> BUNDLED_FONT_RESOURCES = List.of(
        "/fonts/simkai.ttf", "/fonts/simhei.ttf", "/fonts/NotoSansSC-Regular.otf");
    /** 系统字体目录：本机 Windows 优先，其次容器/服务器常见路径。 */
    private static final List<String> FONT_DIRECTORIES = List.of(
        "C:/Windows/Fonts", "/usr/share/fonts", "/usr/local/share/fonts", "/usr/share/fonts/opentype");

    @Value("${report.font-title:auto}") private String titleFontPath;
    @Value("${report.font-body:auto}") private String bodyFontPath;
    @Value("${report.output-dir:}") private String outputDir;

    // ---- 框格模型 ----

    /** 把一条报告映射成规定框格：基础信息 / 检测数据 / 异常现象描述 / 处理与归因 / 签字栏。 */
    public List<DocSection> sections(ReportRecord report) {
        return sections(report, true);
    }

    /**
     * 框格构造。includeAnalysis=false 用于「归因分析的输入正文」：
     * 归因不能把上一次的归因结论当依据 —— 否则关键词规则会在自己上一轮的结论里再匹配一遍，
     * 越跑原因越多，等于规则自己证明自己。
     */
    private List<DocSection> sections(ReportRecord report, boolean includeAnalysis) {
        ReportTemplate.GasRule gas = ReportTemplate.gasRule(report.gasType());
        List<DocSection> sections = new ArrayList<>();
        List<Row> base = new ArrayList<>();
        base.add(new Row("报告编号", report.reportId()));
        base.add(new Row("任务名称", report.taskTitle()));
        base.add(new Row("检测时间", report.detectedAt()));
        base.add(new Row("班次", report.shift()));
        base.add(new Row("检测地点", report.location()));
        base.add(new Row("执行组员", report.member()));
        base.add(new Row("填报人", report.reporter() + (report.reporterPosition() == null ? "" : " · " + report.reporterPosition())));
        base.add(new Row("提交时间", STAMP.format(report.submittedAt().atZone(ZoneId.systemDefault()))));
        sections.add(new DocSection("一、基础信息", base));

        List<Row> data = new ArrayList<>();
        data.add(new Row("气体类型", report.gasLabel() + "（" + report.gasType() + "）"));
        data.add(new Row("检测数值", Texts.plain(report.value()) + " " + report.unit()));
        data.add(new Row("报警阈值", Texts.plain(report.threshold()) + " " + report.unit()));
        data.add(new Row("报警方向", "LOW".equals(report.direction()) ? "低于阈值报警" : "高于阈值报警"));
        data.add(new Row("判定结论", report.judgment() + "（严重度：" + report.severity() + "）"));
        data.add(new Row("执行依据", gas == null ? "-" : gas.standard()));
        sections.add(new DocSection("二、检测数据", data));

        List<Row> abnormal = new ArrayList<>();
        abnormal.add(new Row("异常现象描述", report.phenomenon()));
        abnormal.add(new Row("已采取措施", report.measures() == null || report.measures().isBlank() ? "无" : report.measures()));
        sections.add(new DocSection("三、异常现象描述", abnormal));

        // SOP 执行情况：填报时给出的结构化答案，是「人工问题 / 技能问题」归因的过程证据
        List<Row> sop = new ArrayList<>();
        sop.add(new Row("SOP 执行情况", sopStatusLabel(report.sopStatus())));
        if (report.sopDeviation() != null && !report.sopDeviation().isBlank()) {
            sop.add(new Row("SOP 偏差说明", report.sopDeviation()));
        }
        sections.add(new DocSection("四、SOP 执行情况", sop));

        Map<String, Object> analysis = report.analysis();
        if (analysis != null && includeAnalysis) {
            List<Row> agent = new ArrayList<>();
            agent.add(new Row("分析来源", String.valueOf(analysis.getOrDefault("source_label", "内置规则引擎 v1"))));
            agent.add(new Row("归因结论", String.valueOf(analysis.getOrDefault("conclusion", ""))));
            agent.add(new Row("可能原因", join(analysis.get("causes"))));
            agent.add(new Row("建议措施", join(analysis.get("actions"))));
            agent.add(new Row("命中规则", join(analysis.get("rule_refs"))));
            agent.add(new Row("置信度", String.valueOf(analysis.getOrDefault("confidence", "")) + "（需人工确认后闭环）"));
            sections.add(new DocSection("五、AI 归因分析", agent));
        }
        return sections;
    }

    /** SOP 执行情况的中文标签：空串是字段上线前的历史报告，据实写「未填报」，不当成「已按 SOP」。 */
    private static String sopStatusLabel(String status) {
        return switch (status == null ? "" : status.strip()) {
            case "FOLLOWED" -> "已按 SOP 执行";
            case "DEVIATED" -> "未按 SOP 执行";
            case "NOT_APPLICABLE" -> "本次无对应 SOP";
            default -> "未填报（字段上线前的历史报告）";
        };
    }

    /** 文档正文（AI Agent 读取的内容，重点包含检测数值与现象描述）。 */
    public String extractText(List<DocSection> sections) {
        StringBuilder builder = new StringBuilder();
        for (DocSection section : sections) {
            builder.append(section.title()).append('\n');
            for (Row row : section.rows()) {
                if (row.label() == null) builder.append(row.value()).append('\n');
                else builder.append(row.label()).append('：').append(row.value()).append('\n');
            }
        }
        return builder.toString();
    }

    public String extractText(ReportRecord report) { return extractText(sections(report)); }

    /** 归因分析的输入正文：只含报告本体（基础信息 / 检测数据 / 异常现象描述），不含归因那一节。 */
    public String extractSourceText(ReportRecord report) { return extractText(sections(report, false)); }

    // ---- PDF ----

    public byte[] renderPdf(ReportRecord report) throws IOException {
        List<DocSection> sections = sections(report);
        List<Closeable> fontResources = new ArrayList<>();
        try (PDDocument document = new PDDocument(); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            PDFont titleFont = loadFont(document, titleFontPath, TITLE_FONT_NAMES, fontResources);
            PDFont bodyFont = loadFont(document, bodyFontPath, BODY_FONT_NAMES, fontResources);
            PDPage page = new PDPage(PDRectangle.A4);
            document.addPage(page);
            PDPageContentStream stream = new PDPageContentStream(document, page);
            float cursor = PAGE_HEIGHT - 56f;

            cursor = drawCentered(stream, reportDocumentTitle(), titleFont, 16.5f, cursor, 0.11f, 0.19f, 0.33f);
            cursor -= 6f;
            String meta = "报告编号：" + report.reportId() + "    生成时间："
                + STAMP.format(java.time.Instant.now().atZone(ZoneId.systemDefault()))
                + "    执行组员：" + report.member() + "    填报人：" + report.reporter();
            cursor = drawCentered(stream, meta, bodyFont, 8.5f, cursor, 0.48f, 0.56f, 0.68f);
            cursor -= 10f;
            stream.setStrokingColor(0.78f, 0.83f, 0.90f);
            stream.setLineWidth(0.8f);
            stream.moveTo(MARGIN, cursor);
            stream.lineTo(PAGE_WIDTH - MARGIN, cursor);
            stream.stroke();
            cursor -= 16f;

            for (DocSection section : sections) {
                if (cursor < BOTTOM_LIMIT + 90f) {
                    stream.close();
                    page = new PDPage(PDRectangle.A4);
                    document.addPage(page);
                    stream = new PDPageContentStream(document, page);
                    cursor = PAGE_HEIGHT - 56f;
                }
                cursor = drawSectionHeader(stream, section.title(), titleFont, cursor);
                for (Row row : section.rows()) {
                    float[] size = measureRow(row, bodyFont, PAGE_WIDTH - 2 * MARGIN - LABEL_WIDTH - 16f);
                    if (cursor - size[1] < BOTTOM_LIMIT) {
                        stream.close();
                        page = new PDPage(PDRectangle.A4);
                        document.addPage(page);
                        stream = new PDPageContentStream(document, page);
                        cursor = PAGE_HEIGHT - 56f;
                        cursor = drawSectionHeader(stream, section.title() + "（续）", titleFont, cursor);
                    }
                    cursor = drawRow(stream, row, bodyFont, cursor, size);
                }
                cursor -= 10f;
            }

            if (cursor - SIGNATURE_HEIGHT < BOTTOM_LIMIT) {
                stream.close();
                page = new PDPage(PDRectangle.A4);
                document.addPage(page);
                stream = new PDPageContentStream(document, page);
                cursor = PAGE_HEIGHT - 56f;
            }
            cursor = drawSignatureBoxes(stream, titleFont, bodyFont, cursor);
            stream.close();
            drawFooters(document, bodyFont);
            document.save(out);
            return out.toByteArray();
        } finally {
            fontResources.forEach(ReportDocumentService::closeQuietly);
        }
    }

    private String reportDocumentTitle() { return ReportTemplate.DOCUMENT_TITLE; }

    private float drawSectionHeader(PDPageContentStream stream, String title, PDFont font, float cursor) throws IOException {
        float height = 21f;
        stream.setNonStrokingColor(0.93f, 0.95f, 0.99f);
        stream.addRect(MARGIN, cursor - height, PAGE_WIDTH - 2 * MARGIN, height);
        stream.fill();
        stream.setNonStrokingColor(0.17f, 0.25f, 0.40f);
        stream.beginText();
        stream.setFont(font, 11f);
        stream.newLineAtOffset(MARGIN + 8f, cursor - height + 6.4f);
        stream.showText(safe(title, font));
        stream.endText();
        return cursor - height;
    }

    private float[] measureRow(Row row, PDFont font, float valueWidth) throws IOException {
        float labelWidth = row.label() == null ? 0f : LABEL_WIDTH;
        float available = labelWidth == 0f ? PAGE_WIDTH - 2 * MARGIN - 16f : valueWidth;
        List<String> lines = wrap(safe(row.value(), font), font, 10f, available);
        float height = Math.max(20f, lines.size() * 14f + 7f);
        return new float[] { lines.size(), height, labelWidth };
    }

    private float drawRow(PDPageContentStream stream, Row row, PDFont font, float cursor, float[] size) throws IOException {
        float labelWidth = size[2];
        float totalWidth = PAGE_WIDTH - 2 * MARGIN;
        float height = size[1];
        float valueWidth = totalWidth - labelWidth;

        if (labelWidth > 0f) {
            stream.setNonStrokingColor(0.97f, 0.98f, 0.99f);
            stream.addRect(MARGIN, cursor - height, labelWidth, height);
            stream.fill();
            stream.setNonStrokingColor(0.36f, 0.44f, 0.56f);
            stream.beginText();
            stream.setFont(font, 10f);
            stream.newLineAtOffset(MARGIN + 8f, cursor - 14f);
            stream.showText(safe(row.label(), font));
            stream.endText();
        }
        stream.setNonStrokingColor(0.11f, 0.17f, 0.29f);
        float textY = cursor - 14f;
        for (String line : wrap(safe(row.value(), font), font, 10f, valueWidth - 16f)) {
            stream.beginText();
            stream.setFont(font, 10f);
            stream.newLineAtOffset(MARGIN + labelWidth + 8f, textY);
            stream.showText(line);
            stream.endText();
            textY -= 14f;
        }
        stream.setStrokingColor(0.84f, 0.88f, 0.93f);
        stream.setLineWidth(0.5f);
        stream.addRect(MARGIN, cursor - height, totalWidth, height);
        stream.stroke();
        if (labelWidth > 0f) {
            stream.moveTo(MARGIN + labelWidth, cursor);
            stream.lineTo(MARGIN + labelWidth, cursor - height);
            stream.stroke();
        }
        return cursor - height;
    }

    private float drawSignatureBoxes(PDPageContentStream stream, PDFont titleFont, PDFont bodyFont, float cursor) throws IOException {
        List<String> boxes = ReportTemplate.SIGN_BOXES;
        float totalWidth = PAGE_WIDTH - 2 * MARGIN;
        float boxWidth = totalWidth / boxes.size();
        float height = SIGNATURE_HEIGHT;
        if (cursor - height < BOTTOM_LIMIT) return cursor;
        for (int index = 0; index < boxes.size(); index++) {
            float x = MARGIN + index * boxWidth;
            stream.setStrokingColor(0.84f, 0.88f, 0.93f);
            stream.setLineWidth(0.5f);
            stream.addRect(x, cursor - height, boxWidth, height);
            stream.stroke();
            stream.setNonStrokingColor(0.36f, 0.44f, 0.56f);
            stream.beginText();
            stream.setFont(bodyFont, 9.5f);
            stream.newLineAtOffset(x + 8f, cursor - 15f);
            stream.showText(safe(boxes.get(index) + "：", bodyFont));
            stream.endText();
        }
        return cursor - height - 12f;
    }

    /** 页脚逐页写各自的页码：整份文档共用一个内容流时，每页页码会叠在同一处，读出来是“第 12 页”。 */
    private void drawFooters(PDDocument document, PDFont font) throws IOException {
        int pageCount = document.getNumberOfPages();
        for (int index = 1; index <= pageCount; index++) {
            PDPage page = document.getPage(index - 1);
            try (PDPageContentStream stream = new PDPageContentStream(
                    document, page, PDPageContentStream.AppendMode.APPEND, true, true)) {
                stream.setNonStrokingColor(0.55f, 0.62f, 0.72f);
                stream.beginText();
                stream.setFont(font, 8f);
                stream.newLineAtOffset(MARGIN, 42f);
                stream.showText(FOOTER_NOTE);
                stream.endText();
                stream.beginText();
                stream.setFont(font, 8f);
                stream.newLineAtOffset(PAGE_WIDTH - MARGIN - 52f, 42f);
                stream.showText("第 " + index + " 页 / 共 " + pageCount + " 页");
                stream.endText();
            }
        }
    }

    private float drawCentered(PDPageContentStream stream, String text, PDFont font, float size, float cursor,
                               float red, float green, float blue) throws IOException {
        String value = safe(text, font);
        float width = font.getStringWidth(value) / 1000f * size;
        stream.setNonStrokingColor(red, green, blue);
        stream.beginText();
        stream.setFont(font, size);
        stream.newLineAtOffset((PAGE_WIDTH - width) / 2f, cursor - size);
        stream.showText(value);
        stream.endText();
        return cursor - size - 6f;
    }

    /** 中文字体解析：显式配置 → 内置资源 → 系统字体目录，全部失败时给出已尝试清单。 */
    private PDFont loadFont(PDDocument document, String configured, List<String> preferredNames,
        List<Closeable> resources) throws IOException {
        List<String> tried = new ArrayList<>();
        PDFont font = tryLoadFont(document, configured, resources, tried);
        if (font != null) return font;
        for (String bundled : BUNDLED_FONT_RESOURCES) {
            font = tryLoadFont(document, "classpath:" + bundled, resources, tried);
            if (font != null) return font;
        }
        for (String directory : FONT_DIRECTORIES) {
            for (String name : preferredNames) {
                for (File file : findFontFiles(new File(directory), name)) {
                    font = tryLoadFont(document, file.getAbsolutePath(), resources, tried);
                    if (font != null) return font;
                }
            }
        }
        throw new IOException("未找到可用的中文字体，报告文档无法生成。已尝试：" + String.join(", ", tried)
            + "；请用 report.font-body / REPORT_FONT_BODY 指定字体文件，或给运行镜像安装 CJK 字体。");
    }

    /** 支持 classpath: 资源、TTF/OTF 单文件、TTC/OTC 字体集合；单个候选失败只记录并继续。 */
    private PDFont tryLoadFont(PDDocument document, String location, List<Closeable> resources, List<String> tried) {
        if (location == null || location.isBlank()) return null;
        String spec = location.trim();
        tried.add(spec);
        try {
            if (spec.regionMatches(true, 0, "classpath:", 0, 10)) {
                String resource = spec.substring(10);
                if (!resource.startsWith("/")) resource = "/" + resource;
                try (InputStream stream = ReportDocumentService.class.getResourceAsStream(resource)) {
                    if (stream == null) return null;
                    return chosen(PDType0Font.load(document, stream, true), spec);
                }
            }
            File file = new File(spec);
            if (!file.isFile()) return null;
            if (isCollection(file)) {
                TrueTypeCollection collection = new TrueTypeCollection(file);
                resources.add(collection);
                return chosen(PDType0Font.load(document, pickSimplified(collection), true), spec);
            }
            return chosen(PDType0Font.load(document, file), spec);
        } catch (IOException | RuntimeException error) {
            log.warn("中文字体 {} 加载失败：{}", spec, error.getMessage());
            return null;
        }
    }

    /** 字体集合（.ttc/.otc）优先取简体中文字体，其次取第一个。 */
    private TrueTypeFont pickSimplified(TrueTypeCollection collection) throws IOException {
        List<TrueTypeFont> fonts = new ArrayList<>();
        collection.processAllFonts(fonts::add);
        TrueTypeFont fallback = null;
        for (TrueTypeFont font : fonts) {
            String name = font.getName();
            if (name != null && name.contains("SC")) return font;
            if (fallback == null) fallback = font;
        }
        if (fallback == null) throw new IOException("字体集合中没有可用字体");
        return fallback;
    }

    private PDFont chosen(PDFont font, String location) {
        log.info("报告文档内嵌字体：{}", location);
        return font;
    }

    private boolean isCollection(File file) {
        String name = file.getName().toLowerCase(Locale.ROOT);
        return name.endsWith(".ttc") || name.endsWith(".otc");
    }

    private List<File> findFontFiles(File directory, String name) {
        List<File> matches = new ArrayList<>();
        collectFontFiles(directory, name, 0, matches);
        return matches;
    }

    private void collectFontFiles(File directory, String name, int depth, List<File> matches) {
        if (depth > 4 || matches.size() >= 2) return;
        File[] children = directory.listFiles();
        if (children == null) return;
        for (File child : children) {
            if (child.isDirectory()) collectFontFiles(child, name, depth + 1, matches);
            else if (child.getName().equalsIgnoreCase(name)) matches.add(child);
        }
    }

    private static void closeQuietly(Closeable closeable) {
        try {
            closeable.close();
        } catch (IOException error) {
            log.warn("字体资源释放失败：{}", error.getMessage());
        }
    }

    private List<String> wrap(String text, PDFont font, float size, float maxWidth) throws IOException {
        List<String> lines = new ArrayList<>();
        if (text == null || text.isEmpty()) { lines.add(""); return lines; }
        for (String paragraph : text.replace("\r\n", "\n").replace('\r', '\n').split("\n")) {
            StringBuilder line = new StringBuilder();
            float width = 0f;
            for (String token : tokenize(paragraph)) {
                float tokenWidth = widthOf(token, font, size);
                if (width + tokenWidth > maxWidth && line.length() > 0) {
                    lines.add(line.toString());
                    line.setLength(0);
                    width = 0f;
                    if (token.isBlank()) continue;
                }
                line.append(token);
                width += tokenWidth;
            }
            lines.add(line.toString());
        }
        return lines;
    }

    /** 中文按字断行，连续 ASCII（数字、单位）整体不断行。 */
    private List<String> tokenize(String paragraph) {
        List<String> tokens = new ArrayList<>();
        StringBuilder ascii = new StringBuilder();
        for (int index = 0; index < paragraph.length(); index++) {
            char ch = paragraph.charAt(index);
            if (ch < 128 && !Character.isSpaceChar(ch)) {
                ascii.append(ch);
            } else {
                if (ascii.length() > 0) { tokens.add(ascii.toString()); ascii.setLength(0); }
                tokens.add(String.valueOf(ch));
            }
        }
        if (ascii.length() > 0) tokens.add(ascii.toString());
        return tokens;
    }

    private float widthOf(String token, PDFont font, float size) {
        try {
            return font.getStringWidth(token) / 1000f * size;
        } catch (IOException | IllegalArgumentException error) {
            return token.length() * size;
        }
    }

    private String safe(String text, PDFont font) {
        if (text == null) return "";
        StringBuilder builder = new StringBuilder();
        for (char ch : text.toCharArray()) {
            // 换行由 wrap() 负责分段，不能用字体的宽度查询把它换成“?”（多行内容会挤成一行加问号）
            if (ch == '\n' || ch == '\r') {
                builder.append(ch);
                continue;
            }
            try {
                font.getStringWidth(String.valueOf(ch));
                builder.append(ch);
            } catch (IOException | IllegalArgumentException error) {
                builder.append('?');
            }
        }
        return builder.toString();
    }

    // ---- Word ----

    public byte[] renderDocx(ReportRecord report) throws IOException {
        List<DocSection> sections = sections(report);
        try (XWPFDocument document = new XWPFDocument(); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            XWPFParagraph title = document.createParagraph();
            title.setAlignment(ParagraphAlignment.CENTER);
            XWPFRun titleRun = title.createRun();
            titleRun.setText(ReportTemplate.DOCUMENT_TITLE);
            titleRun.setBold(true);
            titleRun.setFontSize(18);
            applyFont(titleRun, "黑体");

            XWPFParagraph meta = document.createParagraph();
            meta.setAlignment(ParagraphAlignment.CENTER);
            XWPFRun metaRun = meta.createRun();
            metaRun.setText("报告编号：" + report.reportId() + "    生成时间："
                + STAMP.format(java.time.Instant.now().atZone(ZoneId.systemDefault()))
                + "    执行组员：" + report.member() + "    填报人：" + report.reporter());
            metaRun.setFontSize(9);
            metaRun.setColor("7B8BA3");
            applyFont(metaRun, "等线");

            for (DocSection section : sections) {
                XWPFParagraph heading = document.createParagraph();
                heading.setSpacingBefore(160);
                XWPFRun headingRun = heading.createRun();
                headingRun.setText(section.title());
                headingRun.setBold(true);
                headingRun.setFontSize(11);
                headingRun.setColor("2C4166");
                applyFont(headingRun, "黑体");

                XWPFTable table = document.createTable(section.rows().size(), 2);
                table.setWidth("100%");
                applyBorders(table);

                for (int index = 0; index < section.rows().size(); index++) {
                    Row row = section.rows().get(index);
                    XWPFTableRow builtinRow = table.getRow(index);
                    fillCell(builtinRow.getCell(0), row.label() == null ? "" : row.label(), false, 10, "5A6F8F");
                    fillCell(builtinRow.getCell(1), row.value(), false, 10, "1D3155");
                }
                document.createParagraph();
            }

            XWPFTable signature = document.createTable(1, ReportTemplate.SIGN_BOXES.size());
            signature.setWidth("100%");
            applyBorders(signature);
            for (int index = 0; index < ReportTemplate.SIGN_BOXES.size(); index++) {
                fillCell(signature.getRow(0).getCell(index), ReportTemplate.SIGN_BOXES.get(index) + "：", false, 10, "5A6F8F");
            }

            XWPFParagraph footer = document.createParagraph();
            XWPFRun footerRun = footer.createRun();
            footerRun.setText("本报告由系统按“实操任务检测报告”模板框格自动生成，加盖签字后方可归档。");
            footerRun.setFontSize(8);
            footerRun.setColor("8A99AF");
            applyFont(footerRun, "等线");

            document.write(out);
            return out.toByteArray();
        }
    }

    private void applyBorders(XWPFTable table) {
        table.setInsideHBorder(XWPFBorderType.SINGLE, 4, 0, "D8E0EC");
        table.setInsideVBorder(XWPFBorderType.SINGLE, 4, 0, "D8E0EC");
        table.setTopBorder(XWPFBorderType.SINGLE, 4, 0, "D8E0EC");
        table.setBottomBorder(XWPFBorderType.SINGLE, 4, 0, "D8E0EC");
        table.setLeftBorder(XWPFBorderType.SINGLE, 4, 0, "D8E0EC");
        table.setRightBorder(XWPFBorderType.SINGLE, 4, 0, "D8E0EC");
    }

    private void fillCell(XWPFTableCell cell, String text, boolean bold, int fontSize, String color) {
        XWPFParagraph paragraph = cell.getParagraphs().isEmpty() ? cell.addParagraph() : cell.getParagraphs().get(0);
        XWPFRun run = paragraph.createRun();
        run.setBold(bold);
        run.setFontSize(fontSize);
        run.setColor(color);
        applyFont(run, "等线");
        String[] lines = (text == null ? "" : text).split("\n", -1);
        for (int index = 0; index < lines.length; index++) {
            if (index > 0) run.addBreak();
            run.setText(lines[index]);
        }
    }

    private void applyFont(XWPFRun run, String fontName) {
        run.setFontFamily(fontName);
        CTRPr properties = run.getCTR().isSetRPr() ? run.getCTR().getRPr() : run.getCTR().addNewRPr();
        CTFonts fonts = properties.sizeOfRFontsArray() > 0 ? properties.getRFontsArray(0) : properties.addNewRFonts();
        fonts.setAscii(fontName);
        fonts.setHAnsi(fontName);
        fonts.setEastAsia(fontName);
    }

    private static String join(Object value) {
        if (value instanceof List<?> list) {
            List<String> parts = new ArrayList<>();
            for (int index = 0; index < list.size(); index++) parts.add((index + 1) + ". " + list.get(index));
            return String.join("\n", parts);
        }
        return value == null ? "" : String.valueOf(value);
    }
}

package com.power.train.material;

import java.io.ByteArrayInputStream;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;
import org.apache.poi.ss.usermodel.Cell;
import org.apache.poi.ss.usermodel.DataFormatter;
import org.apache.poi.ss.usermodel.Row;
import org.apache.poi.ss.usermodel.Sheet;
import org.apache.poi.ss.usermodel.Workbook;
import org.apache.poi.xslf.usermodel.XMLSlideShow;
import org.apache.poi.xslf.usermodel.XSLFShape;
import org.apache.poi.xslf.usermodel.XSLFSlide;
import org.apache.poi.xslf.usermodel.XSLFTextShape;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.apache.poi.xwpf.usermodel.IBodyElement;
import org.apache.poi.xwpf.usermodel.XWPFDocument;
import org.apache.poi.xwpf.usermodel.XWPFParagraph;
import org.apache.poi.xwpf.usermodel.XWPFTable;
import org.apache.poi.xwpf.usermodel.XWPFTableCell;
import org.apache.poi.xwpf.usermodel.XWPFTableRow;
import org.springframework.stereotype.Component;

/**
 * 文档正文读取：PDF / Word / 文本 / 表格 / 演示文稿都读真实内容，每段都带出处标号
 * （第 N 页 / 第 N 段 / 工作表第 N 行 / 第 N 张幻灯片），管理员审核时能对着原文核对 Agent 的理解。
 * 不假装读到了内容：扫描件没有文字层时直接说明，请先做 OCR 或换成可复制文字的文档。
 */
@Component
public class MaterialTextReader {

    /** 读到的一段正文：label 是出处标号，text 是这一段的内容。 */
    public record Segment(String label, String text) {}

    /** 读取结果：正文分段 + 页数 + 字数 + 读取说明（截断、无文字层等都会说清楚）。 */
    public record Extracted(List<Segment> segments, int pages, int charCount, String note) {
        public String text() {
            StringBuilder builder = new StringBuilder();
            for (Segment segment : segments) {
                builder.append(segment.text()).append('\n');
            }
            return builder.toString();
        }

        public boolean empty() {
            return segments.isEmpty();
        }
    }

    /** 支持读正文的文档类型。 */
    public static final List<String> READABLE = List.of("pdf", "docx", "txt", "md", "csv", "xlsx", "pptx");

    private static final int MAX_PAGES = 200;
    private static final int MAX_CHARS = 200_000;

    public static String extension(String fileName) {
        int dot = fileName == null ? -1 : fileName.lastIndexOf('.');
        return dot < 0 || dot == fileName.length() - 1 ? "" : fileName.substring(dot + 1).toLowerCase();
    }

    public static boolean readable(String fileName) {
        return READABLE.contains(extension(fileName));
    }

    public Extracted read(String fileName, byte[] bytes) {
        if (bytes == null || bytes.length == 0) {
            return new Extracted(List.of(), 0, 0, "文件内容为空");
        }
        try {
            return switch (extension(fileName)) {
                case "pdf" -> pdf(bytes);
                case "docx" -> docx(bytes);
                case "xlsx" -> xlsx(bytes);
                case "pptx" -> pptx(bytes);
                case "txt", "md", "csv" -> plain(bytes);
                default -> new Extracted(List.of(), 0, 0,
                    "不支持的文档类型：" + extension(fileName) + "，可识别 " + String.join(" / ", READABLE));
            };
        } catch (Exception error) {
            return new Extracted(List.of(), 0, 0, "文档读取失败：" + error.getClass().getSimpleName()
                + (error.getMessage() == null ? "" : "：" + error.getMessage()));
        }
    }

    private Extracted pdf(byte[] bytes) throws Exception {
        List<Segment> segments = new ArrayList<>();
        int pages;
        try (PDDocument document = Loader.loadPDF(bytes)) {
            pages = document.getNumberOfPages();
            int limit = Math.min(pages, MAX_PAGES);
            for (int page = 1; page <= limit; page++) {
                PDFTextStripper stripper = new PDFTextStripper();
                stripper.setStartPage(page);
                stripper.setEndPage(page);
                stripper.setSortByPosition(true);
                String text = stripper.getText(document).strip();
                if (!text.isEmpty()) {
                    segments.add(new Segment("第 " + page + " 页", text));
                }
            }
        }
        if (segments.isEmpty()) {
            return new Extracted(List.of(), pages, 0, "PDF 共 " + pages
                + " 页，但没有读到文字层（多为扫描件或图片版），请先做 OCR 或改用可复制文字的 PDF");
        }
        String note = pages > MAX_PAGES ? "文档共 " + pages + " 页，只解析了前 " + MAX_PAGES + " 页" : "";
        return finish(segments, pages, note);
    }

    private Extracted docx(byte[] bytes) throws Exception {
        List<Segment> segments = new ArrayList<>();
        try (XWPFDocument document = new XWPFDocument(new ByteArrayInputStream(bytes))) {
            int index = 0;
            for (IBodyElement element : document.getBodyElements()) {
                String text = "";
                if (element instanceof XWPFParagraph paragraph) {
                    text = paragraph.getText();
                } else if (element instanceof XWPFTable table) {
                    text = tableText(table);
                }
                if (text == null || text.isBlank()) continue;
                index++;
                segments.add(new Segment("第 " + index + " 段", text.strip()));
            }
        }
        if (segments.isEmpty()) {
            return new Extracted(List.of(), 0, 0, "Word 文档里没有读到正文（可能整篇都是图片或嵌入对象）");
        }
        return finish(segments, 0, "");
    }

    private static String tableText(XWPFTable table) {
        StringBuilder builder = new StringBuilder();
        for (XWPFTableRow row : table.getRows()) {
            List<String> cells = new ArrayList<>();
            for (XWPFTableCell cell : row.getTableCells()) {
                cells.add(cell.getText().strip());
            }
            builder.append(String.join(" | ", cells)).append('\n');
        }
        return builder.toString().strip();
    }

    private Extracted xlsx(byte[] bytes) throws Exception {
        List<Segment> segments = new ArrayList<>();
        DataFormatter formatter = new DataFormatter();
        try (Workbook workbook = new XSSFWorkbook(new ByteArrayInputStream(bytes))) {
            for (Sheet sheet : workbook) {
                int rowNo = 0;
                for (Row row : sheet) {
                    rowNo++;
                    List<String> cells = new ArrayList<>();
                    for (Cell cell : row) {
                        String value = formatter.formatCellValue(cell).strip();
                        if (!value.isEmpty()) cells.add(value);
                    }
                    if (cells.isEmpty()) continue;
                    segments.add(new Segment(sheet.getSheetName() + " 第 " + rowNo + " 行", String.join(" | ", cells)));
                }
            }
        }
        if (segments.isEmpty()) {
            return new Extracted(List.of(), 0, 0, "表格里没有读到文字内容");
        }
        return finish(segments, 0, "");
    }

    private Extracted pptx(byte[] bytes) throws Exception {
        List<Segment> segments = new ArrayList<>();
        try (XMLSlideShow slideShow = new XMLSlideShow(new ByteArrayInputStream(bytes))) {
            int index = 0;
            for (XSLFSlide slide : slideShow.getSlides()) {
                index++;
                StringBuilder builder = new StringBuilder();
                for (XSLFShape shape : slide.getShapes()) {
                    if (shape instanceof XSLFTextShape textShape) {
                        builder.append(textShape.getText()).append('\n');
                    }
                }
                String text = builder.toString().strip();
                if (!text.isEmpty()) {
                    segments.add(new Segment("第 " + index + " 张幻灯片", text));
                }
            }
        }
        if (segments.isEmpty()) {
            return new Extracted(List.of(), 0, 0, "演示文稿里没有读到文字内容");
        }
        return finish(segments, 0, "");
    }

    private Extracted plain(byte[] bytes) {
        String text = decode(bytes);
        List<Segment> segments = new ArrayList<>();
        StringBuilder block = new StringBuilder();
        int blockNo = 0;
        for (String line : text.split("\r\n|\r|\n")) {
            if (line.isBlank()) {
                if (!block.isEmpty()) {
                    segments.add(new Segment("第 " + (++blockNo) + " 段", block.toString().strip()));
                    block.setLength(0);
                }
                continue;
            }
            block.append(line.strip()).append('\n');
        }
        if (!block.isEmpty()) {
            segments.add(new Segment("第 " + (++blockNo) + " 段", block.toString().strip()));
        }
        if (segments.isEmpty()) {
            return new Extracted(List.of(), 0, 0, "文本文件里没有读到内容");
        }
        return finish(segments, 0, "");
    }

    /** 文本文件按 UTF-8 读取；出现替换字符时按 GB18030 重读（Windows 记事本常见编码）。 */
    private static String decode(byte[] bytes) {
        String utf8 = new String(bytes, StandardCharsets.UTF_8);
        long broken = utf8.chars().filter(ch -> ch == 0xFFFD).count();
        if (broken > 0) {
            String gbk = new String(bytes, Charset.forName("GB18030"));
            if (gbk.chars().filter(ch -> ch == 0xFFFD).count() < broken) {
                utf8 = gbk;
            }
        }
        return utf8.startsWith("\uFEFF") ? utf8.substring(1) : utf8;
    }

    /** 收口：统一裁剪超长正文并给出字数，避免几十万字的文档把接口拖慢。 */
    private Extracted finish(List<Segment> segments, int pages, String note) {
        List<Segment> kept = new ArrayList<>();
        int count = 0;
        boolean truncated = false;
        for (Segment segment : segments) {
            if (count >= MAX_CHARS) {
                truncated = true;
                break;
            }
            String text = segment.text();
            if (count + text.length() > MAX_CHARS) {
                text = text.substring(0, MAX_CHARS - count);
                truncated = true;
            }
            count += text.length();
            kept.add(new Segment(segment.label(), text));
        }
        String merged = note;
        if (truncated) {
            String tail = "正文超长，只解析了前 " + MAX_CHARS + " 字";
            merged = merged.isEmpty() ? tail : merged + "；" + tail;
        }
        return new Extracted(kept, pages, count, merged);
    }
}

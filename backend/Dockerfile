FROM maven:3.9-eclipse-temurin-25 AS build
WORKDIR /app
COPY pom.xml .
RUN mvn -q dependency:go-offline
COPY src src
RUN mvn -q package -DskipTests
FROM eclipse-temurin:25-jre
WORKDIR /app
# 容器内没有 Windows 字体，报告 PDF 内嵌中文需要 CJK 字体（wqy-zenhei / Droid 为 TrueType，PDFBox 兼容性最好）
RUN apt-get update \
 && apt-get install -y --no-install-recommends fonts-wqy-zenhei fonts-droid-fallback \
 && rm -rf /var/lib/apt/lists/*
COPY --from=build /app/target/*.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
# Stage 1: Скачиваем Maven артефакт
FROM maven:3.9-eclipse-temurin-17-alpine AS builder

WORKDIR /build

# Создаём pom.xml для загрузки neo4j-migrations-cli
RUN echo '<?xml version="1.0" encoding="UTF-8"?>' > pom.xml && \
    echo '<project xmlns="http://maven.apache.org/POM/4.0.0"' >> pom.xml && \
    echo '         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"' >> pom.xml && \
    echo '         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">' >> pom.xml && \
    echo '  <modelVersion>4.0.0</modelVersion>' >> pom.xml && \
    echo '  <groupId>temp</groupId>' >> pom.xml && \
    echo '  <artifactId>temp</artifactId>' >> pom.xml && \
    echo '  <version>1.0</version>' >> pom.xml && \
    echo '  <dependencies>' >> pom.xml && \
    echo '    <dependency>' >> pom.xml && \
    echo '      <groupId>eu.michael-simons.neo4j</groupId>' >> pom.xml && \
    echo '      <artifactId>neo4j-migrations-cli</artifactId>' >> pom.xml && \
    echo '      <version>2.17.4</version>' >> pom.xml && \
    echo '    </dependency>' >> pom.xml && \
    echo '  </dependencies>' >> pom.xml && \
    echo '</project>' >> pom.xml

# Загружаем все зависимости
RUN mvn dependency:copy-dependencies -DoutputDirectory=/build/libs

# Stage 2: Финальный образ
FROM eclipse-temurin:17-jre-alpine

# Создаём непривилегированного пользователя для безопасности
RUN addgroup -S neo4j \
    && adduser -S neo4j -G neo4j

WORKDIR /app

# Копируем библиотеки
COPY --from=builder /build/libs /app/libs

# Создаём скрипт запуска с поддержкой переменных окружения и настраиваем права
RUN echo '#!/bin/sh' > /app/neo4j-migrations.sh \
    && echo 'set -e' >> /app/neo4j-migrations.sh \
    && echo '' >> /app/neo4j-migrations.sh \
    && echo '# Запуск с параметрами из переменных окружения' >> /app/neo4j-migrations.sh \
    && echo 'exec java -cp "/app/libs/*" ac.simons.neo4j.migrations.cli.MigrationsCli \' >> /app/neo4j-migrations.sh \
    && echo '  --username "${NEO4J_USERNAME:-neo4j}" \' >> /app/neo4j-migrations.sh \
    && echo '  --password "${NEO4J_PASSWORD}" \' >> /app/neo4j-migrations.sh \
    && echo '  --address "${NEO4J_URI}" \' >> /app/neo4j-migrations.sh \
    && echo '  --location "${NEO4J_MIGRATIONS_LOCATION:-file:///migrations}" \' >> /app/neo4j-migrations.sh \
    && echo '  "$@"' >> /app/neo4j-migrations.sh \
    && chmod +x /app/neo4j-migrations.sh \
    && chown -R neo4j:neo4j /app

# Переключаемся на непривилегированного пользователя
USER neo4j

ENTRYPOINT ["/app/neo4j-migrations.sh"]
CMD ["migrate"]

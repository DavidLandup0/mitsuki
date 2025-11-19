FROM maven:3.9-eclipse-temurin-21 AS build

WORKDIR /app
COPY pom.xml .
RUN mvn dependency:go-offline
COPY src ./src
RUN mvn package -DskipTests


FROM eclipse-temurin:21-jre-jammy

WORKDIR /app
COPY --from=build /app/target/*.jar app.jar
EXPOSE 8000
CMD ["java", "-jar", "app.jar", "--server.port=8000"]

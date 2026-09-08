FROM alpine:latest

RUN apk add --no-cache curl

WORKDIR /app

COPY loadgen.sh /app/loadgen.sh
RUN chmod +x /app/loadgen.sh

CMD ["/app/loadgen.sh"]

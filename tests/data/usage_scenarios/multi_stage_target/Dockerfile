FROM alpine AS builder
RUN echo 'built-in-builder' > /artifact.txt

FROM alpine AS final
COPY --from=builder /artifact.txt /artifact.txt
RUN echo 'stage-final' > /stage.txt

FROM alpine AS other
RUN echo 'stage-other' > /stage.txt

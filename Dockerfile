FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html /usr/share/nginx/html/index.html
COPY data.js /usr/share/nginx/html/data.js
COPY model_config.json /usr/share/nginx/html/model_config.json
COPY benchmark_data.json /usr/share/nginx/html/benchmark_data.json
COPY benchmark_from_aa/ /usr/share/nginx/html/benchmark_from_aa/
COPY js/ /usr/share/nginx/html/js/
EXPOSE 8000
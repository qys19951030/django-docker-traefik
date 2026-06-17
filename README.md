# Dockerizing Django with Postgres, Gunicorn, and Traefik

## 想要自己构建？

请参阅原文 [post](https://testdriven.io/blog/django-docker-traefik/)。

## 如何使用本项目？

### 环境变量说明

| 变量名 | 说明 | 开发默认值 | 生产要求 |
|--------|------|-----------|---------|
| `DEBUG` | Django 调试开关，布尔值，支持 `1/0`、`true/false`、`yes/no`、`on/off` | `1` | **必须为 `0`** |
| `SECRET_KEY` | Django 密钥。**生产模式下不安全的值会直接导致启动失败**（长度 <50、`django-insecure-` 前缀、占位值如 `change-me-to-a-long-random-string`、唯一字符 <5 均被拒绝） | 内置 dev 默认 | **必填，≥50 字符、≥5 种唯一字符、无占位值** |
| `DATABASE_URL` | 数据库连接字符串 | 示例值 | **必填** |
| `DJANGO_ALLOWED_HOSTS` | 允许访问的主机名列表，逗号分隔 | `django.localhost,localhost,127.0.0.1,web` | **必填，至少配置正式域名** |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | CSRF 可信 Origin 列表，逗号分隔；必须含协议头 | 本地 http 域名 | **必填，与 HTTPS 域名匹配** |
| `DJANGO_SECURE_SSL_REDIRECT` | 生产模式是否启用 HTTP→HTTPS 重定向，默认 `1` | 不适用 | 默认 `1`；仅当你确认 Traefik 已在入口层做重定向且不希望 Django 再做时设为 `0` |
| `DJANGO_SECURE_HSTS_SECONDS` | HSTS `max-age`，默认 `31536000`（1 年） | 不适用 | 默认 `31536000`；灰度期可设小值如 `60`，稳定后调回 |
| `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS` | HSTS 是否包含子域，默认 `1` | 不适用 | 默认 `1` |
| `DJANGO_SECURE_HSTS_PRELOAD` | HSTS 是否包含 `preload` 指令，默认 `1` | 不适用 | 默认 `1` |

---

### 开发模式

开发模式使用 `docker-compose.yml`，走 **HTTP** 链路，不启用 SSL 重定向 / HSTS / Secure Cookie。

1. 构建并启动容器：

    ```sh
    docker-compose up -d --build
    ```

2. 访问验证：

    - 应用：http://django.localhost:8008/
    - Traefik 面板：http://django.localhost:8081/

3. 开发模式已预置的环境变量：

    ```env
    DEBUG=1
    DJANGO_ALLOWED_HOSTS=django.localhost,localhost,127.0.0.1,web
    DJANGO_CSRF_TRUSTED_ORIGINS=http://django.localhost:8008,http://localhost:8008,http://127.0.0.1:8008
    ```

---

### 生产模式

生产模式使用 `docker-compose.prod.yml`，Traefik 负责 TLS 终结并将请求通过 HTTP 转发给 Gunicorn，Django 通过 `X-Forwarded-*` 头感知真实的 HTTPS 链路和客户端 Host。

#### 1. 配置前准备

编辑 `docker-compose.prod.yml`，替换以下项：

| 位置 | 替换内容 |
|------|---------|
| `web.environment.SECRET_KEY` | 替换为你的密钥（可用 `python -c "import secrets; print(secrets.token_urlsafe(64))"` 生成） |
| `web.environment.DJANGO_ALLOWED_HOSTS` | 你的实际域名 |
| `web.environment.DJANGO_CSRF_TRUSTED_ORIGINS` | 对应的 HTTPS Origin |
| `services.web.labels` 中的 `Host(` | 替换为你的实际域名 |
| `services.traefik.labels` 中的 `Host(` | 替换为面板域名 |

编辑 `traefik.prod.toml`，将 `certificatesResolvers.letsencrypt.acme.email` 改为你的真实邮箱。

> ⚠️ 仓库自带的 `SECRET_KEY` 值仅作格式参考。**上线前必须替换为你自己的密钥，否则 `change-me-to-a-long-random-string` 等占位值会被启动校验拒绝。**

#### 2. 构建并启动

```sh
docker-compose -f docker-compose.prod.yml up -d --build
```

#### 3. 用 `python manage.py check --deploy` 验证

进入 `web` 容器执行：

```sh
python manage.py check --deploy
```

预期输出：

```
System check identified no issues (0 silenced).
```

如果有任何 `security.W***` 警告，说明安全配置未收口，需要检查对应的环境变量。

#### 4. 手动验证 HTTPS 代理识别

进入 Django shell 模拟一个带代理头的请求：

```python
# python manage.py shell
from django.test import RequestFactory
factory = RequestFactory()
request = factory.get(
    '/',
    HTTP_X_FORWARDED_PROTO='https',
    HTTP_X_FORWARDED_HOST='django-traefik.your-domain.com',
    HTTP_X_FORWARDED_PORT='443',
)
print('is_secure:', request.is_secure())    # True
print('scheme:', request.scheme)            # https
print('host:', request.get_host())          # django-traefik.your-domain.com
print('port:', request.get_port())          # 443
```

---

### 生产安全配置一览

本模板在 `DEBUG=False` 时自动启用的安全项：

| 设置 | 默认值 | 环境变量 | 说明 |
|------|--------|---------|------|
| `SECURE_PROXY_SSL_HEADER` | `('HTTP_X_FORWARDED_PROTO', 'https')` | — | 始终开启，让 Django 通过 Traefik 的 `X-Forwarded-Proto` 头判断 HTTPS |
| `USE_X_FORWARDED_HOST` | `True` | — | 始终开启 |
| `USE_X_FORWARDED_PORT` | `True` | — | 始终开启 |
| `SECURE_SSL_REDIRECT` | `True` | `DJANGO_SECURE_SSL_REDIRECT` | 非 HTTPS 请求 301→HTTPS；配合 `SECURE_PROXY_SSL_HEADER`，已通过 Traefik 转发的 HTTPS 不会误重定向 |
| `SECURE_HSTS_SECONDS` | `31536000` | `DJANGO_SECURE_HSTS_SECONDS` | HSTS max-age=1 年；灰度期可设小值 |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | `True` | `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS` | HSTS 含 includeSubDomains |
| `SECURE_HSTS_PRELOAD` | `True` | `DJANGO_SECURE_HSTS_PRELOAD` | HSTS 含 preload |
| `SESSION_COOKIE_SECURE` | `True` | — | Session Cookie 仅 HTTPS |
| `CSRF_COOKIE_SECURE` | `True` | — | CSRF Cookie 仅 HTTPS |
| `SECURE_CONTENT_TYPE_NOSNIFF` | `True` | — | `X-Content-Type-Options: nosniff` |
| `X_FRAME_OPTIONS` | `DENY` | — | 禁止 iframe 嵌入 |

开发模式（`DEBUG=True`）以上安全项全部关闭，`docker-compose.yml` 的 HTTP 链路正常可用。

#### SECRET_KEY 启动校验

生产模式下，`SECRET_KEY` 会在 Django 启动阶段被校验。以下情况会触发 `ImproperlyConfigured` 异常并阻止启动：

- 长度不足 50 字符
- 以 `django-insecure-` 开头
- 包含已知占位值（如 `change-me-to-a-long-random-string`、`your-secret-key-here`、`replace-me` 等）
- 唯一字符数不足 5 个

开发模式不受此限制。

---

### 运行测试

```sh
cd app
pip install -r requirements.txt

# 1) 测试环境变量解析 + settings 装载 + SECRET_KEY 校验
python -m unittest tests.test_settings -v

# 2) 测试带 X-Forwarded-* 头的真实请求处理 + SSL 重定向 + HSTS
python -m unittest tests.test_request_handling -v

# 3) 一次性运行所有测试
python -m unittest discover -s tests -v
```

预期所有测试 `OK`，无 FAILED / ERROR。如在 Windows / 受限环境下缺少 `gcc` 等导致 `psycopg2-binary` 编译失败，可临时改为 `pip install Django django-environ whitenoise` 再跑（测试用 SQLite 内存库，不依赖 Postgres）。

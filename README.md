# Dockerizing Django with Postgres, Gunicorn, and Traefik

## 想要自己构建？

请参阅原文 [post](https://testdriven.io/blog/django-docker-traefik/)。

## 如何使用本项目？

### 环境变量说明

| 变量名 | 说明 | 示例 | 开发默认值 | 生产要求 |
|--------|------|------|-----------|---------|
| `DEBUG` | Django 调试开关，布尔值，支持 `1/0`、`true/false`、`yes/no`、`on/off`（不区分大小写） | `1`、`0` | `1` | **必须为 `0`** |
| `SECRET_KEY` | Django 密钥，生产环境必须修改为长随机字符串 | 复杂随机串 | 使用内置默认 | **必填，且必须保密** |
| `DATABASE_URL` | 数据库连接字符串 | `postgresql://user:pass@host:5432/db` | 示例值 | **必填** |
| `DJANGO_ALLOWED_HOSTS` | 允许访问的主机名列表，逗号分隔；支持 `.example.com` 通配子域格式 | `django.example.com,.example.com` | `django.localhost,localhost,127.0.0.1,web` | **必填，至少配置正式域名** |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | CSRF 可信 Origin 列表，逗号分隔；必须包含协议头，支持 `*` 通配符 | `https://django.example.com,https://*.example.com` | 本地 http 域名列表 | **必填，与 HTTPS 域名匹配** |

---

### 开发模式

开发模式使用 `docker-compose.yml`，走 **HTTP** 链路，不启用 SSL 强制跳转，Cookie 不要求 `Secure` 属性。

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

编辑 `docker-compose.prod.yml`，替换至少以下项：

| 位置 | 替换内容 |
|------|---------|
| `web.environment.SECRET_KEY` | 生成一个长随机字符串（可用 `python -c "import secrets; print(secrets.token_urlsafe(64))"` 生成） |
| `web.environment.DJANGO_ALLOWED_HOSTS` | 你的实际域名，例如 `app.yourdomain.com,.yourdomain.com` |
| `web.environment.DJANGO_CSRF_TRUSTED_ORIGINS` | 对应的 HTTPS Origin，例如 `https://app.yourdomain.com,https://*.yourdomain.com` |
| `services.web.labels` 中的 `Host(` | 替换为你的实际域名 |
| `services.traefik.labels` 中的 `Host(` | 替换为面板域名 |

编辑 `traefik.prod.toml`，将 `certificatesResolvers.letsencrypt.acme.email` 改为你的真实邮箱（用于 Let's Encrypt 证书申请通知）。

#### 2. 构建并启动

```sh
docker-compose -f docker-compose.prod.yml up -d --build
```

#### 3. 验证 Django 已正确识别 Traefik 转发的 HTTPS 请求

进入 `web` 容器（或本地设置好环境变量），使用 Django shell 模拟一个带代理头的请求：

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
print('is_secure:', request.is_secure())    # 应该输出 True
print('scheme:', request.scheme)            # 应该输出 https
print('host:', request.get_host())          # 应该输出 django-traefik.your-domain.com
print('port:', request.get_port())          # 应该输出 443
```

预期输出：

```
is_secure: True
scheme: https
host: django-traefik.your-domain.com
port: 443
```

如果上面 4 项都符合预期，说明 Django → Traefik 的 HTTPS 代理链配置正确。

---

### 反向代理下的关键安全配置说明

本模板默认开启了以下 **对代理链友好** 的 Django 设置：

| 设置 | 值 | 说明 |
|------|----|------|
| `SECURE_PROXY_SSL_HEADER` | `('HTTP_X_FORWARDED_PROTO', 'https')` | 依据 `X-Forwarded-Proto: https` 判定请求是否安全（由 Traefik 设置）。⚠️ 仅在你确信 **只有 Traefik 才能直连 Django** 时才保持该配置，避免伪造头绕过 HTTPS 判断。 |
| `USE_X_FORWARDED_HOST` | `True` | 优先使用 `X-Forwarded-Host`（Traefik 写入的真实 Host），而不是 Gunicorn 监听的内网主机名。 |
| `USE_X_FORWARDED_PORT` | `True` | 优先使用 `X-Forwarded-Port`，避免 URL 反向拼出内部 `8000` 端口。 |

仅当 `DEBUG=False`（生产）时额外启用的安全项：

| 设置 | 值 | 说明 |
|------|----|------|
| `SESSION_COOKIE_SECURE` | `True` | Session Cookie 仅通过 HTTPS 传输。 |
| `CSRF_COOKIE_SECURE` | `True` | CSRF Cookie 仅通过 HTTPS 传输。 |
| `SECURE_SSL_REDIRECT` | `False` | **不**在 Django 层做 HTTP→HTTPS 跳转（由 `traefik.prod.toml` 的 entryPoint 重定向统一处理）。 |
| `SECURE_HSTS_SECONDS` | `0` | 默认不开启 HSTS，避免误伤；确认证书和跳转都稳定后可自行调大并开启 `SECURE_HSTS_INCLUDE_SUBDOMAINS` / `PRELOAD`。 |
| `SECURE_CONTENT_TYPE_NOSNIFF` | `True` | 写 `X-Content-Type-Options: nosniff`。 |
| `X_FRAME_OPTIONS` | `DENY` | 禁止被嵌入 iframe。 |

开发模式（`DEBUG=True`）不会被强制写入 `SESSION_COOKIE_SECURE` 等生产项，`docker-compose.yml` 的本地 HTTP 链路可以正常使用。

---

### 运行测试

本仓库附带两套验证：**helper 解析层** 和 **真实 settings / 请求行为**。

```sh
cd app
pip install -r requirements.txt

# 1) 测试环境变量解析 + settings 装载行为
python -m unittest tests.test_settings -v

# 2) 测试带 X-Forwarded-* 头的真实请求处理
python -m unittest tests.test_request_handling -v

# 3) 一次性运行所有测试
python -m unittest discover -s tests -v
```

预期所有测试 `OK`，无 FAILED / ERROR。如在 Windows / 受限环境下缺少 `gcc` 等导致 `psycopg2-binary` 编译失败，可临时改为 `pip install Django django-environ whitenoise` 再跑（测试用 SQLite 内存库，不依赖 Postgres）。

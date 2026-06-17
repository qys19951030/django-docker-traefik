# Dockerizing Django with Postgres, Gunicorn, and Traefik

## 想要自己构建？

请参阅原文 [post](https://testdriven.io/blog/django-docker-traefik/)。

## 如何使用本项目？

### 环境变量说明

| 变量名 | 说明 | 开发默认值 | 生产要求 |
|--------|------|-----------|---------|
| `DEBUG` | Django 调试开关，布尔值，支持 `1/0`、`true/false`、`yes/no`、`on/off` | `1` | **必须为 `0`** |
| `SECRET_KEY` | Django 密钥。**生产模式下任何仓库示例值 / 占位值 / 弱密钥都会被启动阶段直接拒绝**，详见下方 [SECRET_KEY 交付说明](#secret_key-交付说明)。 | 内置 dev 默认 | **必须由用户显式提供，长度 ≥50、唯一字符 ≥5、不得为任何仓库示例值** |
| `DATABASE_URL` | 数据库连接字符串 | 示例值 | **必填** |
| `DJANGO_ALLOWED_HOSTS` | 允许访问的主机名列表，逗号分隔 | `django.localhost,localhost,127.0.0.1,web` | **必填，至少配置正式域名** |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | CSRF 可信 Origin 列表，逗号分隔；必须含协议头 | 本地 http 域名 | **必填，与 HTTPS 域名匹配** |
| `DJANGO_SECURE_SSL_REDIRECT` | 生产模式是否启用 HTTP→HTTPS 重定向，默认 `1` | 不适用 | 默认 `1`；仅当你确认 Traefik 已在入口层做重定向且不希望 Django 再做时设为 `0` |
| `DJANGO_SECURE_HSTS_SECONDS` | HSTS `max-age`，默认 `31536000`（1 年） | 不适用 | 默认 `31536000`；灰度期可设小值如 `60`，稳定后调回 |
| `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS` | HSTS 是否包含子域，默认 `1` | 不适用 | 默认 `1` |
| `DJANGO_SECURE_HSTS_PRELOAD` | HSTS 是否包含 `preload` 指令，默认 `1` | 不适用 | 默认 `1` |

---

### SECRET_KEY 交付说明

**`docker-compose.prod.yml` 不再自带可直接上线使用的固定 `SECRET_KEY`。**

生产密钥由用户显式提供，有两种推荐方式：

#### 方式 A：在启动命令前通过 shell 环境变量注入（推荐）

```sh
# 1) 生成一把密钥
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(64))")
#    Windows PowerShell:
#    $env:SECRET_KEY = python -c "import secrets; print(secrets.token_urlsafe(64))"

# 2) 用注入的变量启动
docker compose -f docker-compose.prod.yml up -d --build
```

如果忘记注入，Compose 会立刻报错并中止（因为 `docker-compose.prod.yml` 用了 `${SECRET_KEY:?...}` 语法，fail-fast），不会偷偷拿默认值起容器。

#### 方式 B：通过 `.env.prod` 文件

```sh
# 1) 复制示例文件
cp .env.prod.example .env.prod

# 2) 把 .env.prod 里的 SECRET_KEY=... 改成你自己生成的真实值

# 3) 显式指定 env 文件启动
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
```

> ⚠️ **绝对不能**把 `.env.prod` 提交到 git。`.env.prod.example` 里的 SECRET_KEY 只是占位，会被 Django 启动校验拒绝，不能作为真实值使用。

---

### 开发模式

开发模式使用 `docker-compose.yml`，走 **HTTP** 链路，不启用 SSL 重定向 / HSTS / Secure Cookie，也不校验 SECRET_KEY 的强度。

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

#### 1. 生成你自己的 SECRET_KEY

```sh
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

把输出的随机串保存好，这是你部署实例独有的密钥，不要提交到 git。

#### 2. 配置生产环境

编辑 `docker-compose.prod.yml`，替换：

| 位置 | 替换内容 |
|------|---------|
| `web.environment.DJANGO_ALLOWED_HOSTS` | 你的实际域名 |
| `web.environment.DJANGO_CSRF_TRUSTED_ORIGINS` | 对应的 HTTPS Origin |
| `services.web.labels` 中的 `Host(` | 替换为你的实际域名 |
| `services.traefik.labels` 中的 `Host(` | 替换为面板域名 |

编辑 `traefik.prod.toml`，将 `certificatesResolvers.letsencrypt.acme.email` 改为你的真实邮箱。

> 🔒 **SECRET_KEY 不需要在 `docker-compose.prod.yml` 里写死**，它通过 `${SECRET_KEY:?...}` 从 shell 或 `.env.prod` 读取。任何写在仓库里的示例值都会被 Django 启动阶段拒绝。

#### 3. 注入密钥并启动

```sh
# shell 环境变量注入（方式 A）
export SECRET_KEY=<你刚才生成的长随机串>
docker compose -f docker-compose.prod.yml up -d --build

# 或 .env.prod 文件注入（方式 B）
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
```

#### 4. 验证生产配置链路（3 条 fail-fast + 1 条通过）

你可以按下面 4 步依次验证，确保安全链路上每一环都按预期工作：

##### 4.1 `docker compose config` 能正常解析（提供密钥时）

```sh
SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(64))") \
  docker compose -f docker-compose.prod.yml config
```

预期：Compose 成功渲染完整配置，`services.web.environment.SECRET_KEY` 为你刚才生成的随机串，`DEBUG` 为 `"0"`。

##### 4.2 不提供 `SECRET_KEY` 时 Compose 立刻 fail-fast

```sh
unset SECRET_KEY
docker compose -f docker-compose.prod.yml config
```

预期：Compose 立刻报错并退出非零，错误信息包含 `required variable SECRET_KEY is missing a value`，**不会**偷偷带默认值继续渲染，更不会启动容器。

##### 4.3 提供仓库示例值时 Django 启动阶段拒绝

即使绕过了 Compose 的变量校验（比如有人强行在 compose 文件里写死），Django 自身也会在 settings 加载阶段拒绝仓库中出现过的任何示例值：

```sh
cd app
DEBUG=0 SECRET_KEY='aB3dE7fG9hJ2kL5mN8pQ1rS4tU6vW0xY2zA5bC8dE1fG4hI7jK0lM3nO6pQr' \
  python manage.py check --deploy
```

预期：启动阶段直接抛出 `django.core.exceptions.ImproperlyConfigured: SECRET_KEY is not safe for production.`，exit code = 1，根本走不到 deploy check。

##### 4.4 提供用户自定义有效密钥时 `check --deploy` 通过

```sh
cd app
DEBUG=0 \
  SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(64))") \
  DJANGO_ALLOWED_HOSTS=example.com \
  DJANGO_CSRF_TRUSTED_ORIGINS=https://example.com \
  python manage.py check --deploy
```

预期：`System check identified no issues (0 silenced).`，exit code = 0。

#### 5. 手动验证 HTTPS 代理识别

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

生产模式下，`SECRET_KEY` 会在 Django 启动阶段被校验，以下情况触发 `ImproperlyConfigured` 异常并阻止启动：

- 长度不足 50 字符
- 以 `django-insecure-` 开头
- 包含已知占位值（如 `change-me-to-a-long-random-string`、`replace-me`、`REPLACE-ME-WITH-YOUR-OWN-...`、`test-key-for-check-deploy...` 等）
- 精确命中仓库中出现过的任何示例值（`aB3dE7fG9...nO6pQr`、`django-insecure-*y(bpj*...` 等）
- 唯一字符数不足 5 个

开发模式不受此限制。

---

### 运行测试

```sh
cd app
pip install -r requirements.txt

# 1) 测试环境变量解析 + settings 装载 + SECRET_KEY 校验（含仓库示例值被拒绝）
python -m unittest tests.test_settings -v

# 2) 测试带 X-Forwarded-* 头的真实请求处理 + SSL 重定向 + HSTS
python -m unittest tests.test_request_handling -v

# 3) 一次性运行所有测试
python -m unittest discover -s tests -v
```

预期所有测试 `OK`，无 FAILED / ERROR。如在 Windows / 受限环境下缺少 `gcc` 等导致 `psycopg2-binary` 编译失败，可临时改为 `pip install Django django-environ whitenoise` 再跑（测试用 SQLite 内存库，不依赖 Postgres）。

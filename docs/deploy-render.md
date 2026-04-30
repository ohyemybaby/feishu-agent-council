# Deploy to Render Free

This is the recommended public HTTPS deployment path when local tunnels are blocked.

## 1. Push the Project to GitHub

Create a new GitHub repository, then run these commands from the project folder:

```powershell
git init
git add .
git commit -m "feat: add feishu agent council mvp"
git branch -M main
git remote add origin https://github.com/YOUR_NAME/feishu-agent-council.git
git push -u origin main
```

## 2. Create a Render Web Service

1. Open Render.
2. Choose **New +** -> **Web Service**.
3. Connect the GitHub repository.
4. Render should detect `render.yaml`.
5. Create the service.

The first deploy can run with mock providers:

```text
MOCK_PROVIDERS=true
FEISHU_DRY_RUN=true
```

After the service is live, test:

```text
https://YOUR-RENDER-SERVICE.onrender.com/health
```

## 3. Configure Real Secrets

In Render service settings, add environment variables:

```text
FEISHU_APP_ID=
FEISHU_APP_SECRET=
FEISHU_VERIFICATION_TOKEN=
FEISHU_DRY_RUN=false

MOCK_PROVIDERS=false
GLM_API_KEY=
DEEPSEEK_API_KEY=
```

Keep these values out of Git.

## 4. Configure Feishu Callback

Use this callback URL:

```text
https://YOUR-RENDER-SERVICE.onrender.com/webhooks/feishu
```

In Feishu Open Platform:

1. Create or open an internal app.
2. Enable bot capability.
3. Go to event subscription.
4. Set the request URL to the callback above.
5. Set the verification token to the same value as `FEISHU_VERIFICATION_TOKEN`.
6. Subscribe to message receive events.
7. Publish or enable the app for your tenant.

## Notes

Render free services may sleep after inactivity. The first message after sleep can be slower. This is fine for the MVP and demos.


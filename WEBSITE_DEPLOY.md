# 宣传页（静态 HTML）从本地到上线：简要流程

本流程适用于“一个纯静态页面（`index.html` + `img/` 等资源）”，最终通过 GitHub Pages / Gitee Pages 对外提供访问链接。

## 1. 本地制作

- 在仓库根目录创建或更新 `index.html`
- 静态资源（图片等）建议放在 `img/` 目录下，并使用相对路径引用，例如：
  - `img/image.png`
  - 文件名包含空格时：`img/Observation%20and%20movement.png`

## 2. 本地预览（确认样式与跳转）

在页面目录启动一个本地静态服务，然后用浏览器打开：

```bash
python -m http.server 8080
```

访问：`http://localhost:8080/`

检查项：
- 按钮跳转（arXiv / Code / Benchmark / Method / Gitee）是否正确
- 图片是否能加载（路径、大小写、空格编码）
- 交互效果（例如鼠标悬停立体 tilt）是否正常

## 3. 推送到云端仓库（同步上线的前提）

部署的页面来自仓库里的文件版本，本地改动不会自动同步到线上。

```bash
git add .
git commit -m "Update website"
git push
```

## 4. GitHub Pages 部署（对外可访问）

1. 打开 GitHub 仓库页面 → **Settings** → **Pages**
2. **Build and deployment**
   - Source：Deploy from a branch
   - Branch：`main` 或 `master`
   - Folder：`/(root)`（根目录）
3. 保存后等待 GitHub 发布
4. 访问地址通常是：
   - `https://<用户名>.github.io/<仓库名>/`

更新方式：
- 每次修改后 `git push`，GitHub Pages 通常会自动重新发布（可能有缓存，必要时 Ctrl+F5 强刷）

## 5. Gitee Pages 部署（国内访问更快）

1. 打开 Gitee 仓库页面 → **服务** → **Gitee Pages**
2. 选择部署分支（`main`/`master`）与目录（根目录 `/`）
3. 点击 **启动/更新**
4. 使用 Gitee 提供的 Pages 链接访问

更新方式：
- 通常需要 `git push` 后再到 Gitee Pages 页面点一次“更新/重新部署”（视账号与设置而定）

## 6. 常见问题速查

- 线上 404：
  - Pages 没开启 / 分支选错 / 目录选错
  - 根目录没有 `index.html`（注意大小写）
- 图片不显示：
  - 路径不对、大小写不一致、文件名有空格未编码（用 `%20`）
  - 图片没 push 到仓库
- 更新不生效：
  - GitHub：等 1–3 分钟 + 强刷
  - Gitee：push 后需要手动点“更新/重新部署”


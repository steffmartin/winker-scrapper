"""Autenticação e seleção de portal no Winker."""


def autenticar(page, username, password, wl, portal_index=None):
    # Login no portal
    login_url = f"https://app.winker.com.br/intra/default/login?wl={wl}"
    page.goto(login_url, wait_until="networkidle")
    page.fill("#LoginForm_username", username)
    page.fill("#LoginForm_password", password)
    page.click("#loginform > div.input-group.login-entrar > input")

    try:
        page.wait_for_url(lambda url: "/intra" in url, timeout=60000)
    except Exception:
        pass

    if "escolherPortal" in page.url:
        if portal_index is not None:
            idx = int(portal_index) - 1
            page.locator("#content hgroup > div > table tbody tr").nth(idx).locator("a").first.click()
        else:
            page.locator("#content hgroup > div > table tbody tr").nth(0).locator("a").first.click()

        page.wait_for_url("**/intra", timeout=60000)
    else:
        page.wait_for_url("**/intra", timeout=60000)


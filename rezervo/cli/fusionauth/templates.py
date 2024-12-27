from typing import Optional

from pydantic import BaseModel


def build_setup_password_complete_template(redirect_url: str):
    redirect_tag = (
        f'<meta http-equiv="refresh" content="0; url={redirect_url}" />'
        if redirect_url
        else ""
    )
    return f"""
[#ftl/]
[#-- @ftlvariable name="application" type="io.fusionauth.domain.Application" --]
[#-- @ftlvariable name="client_id" type="java.lang.String" --]
[#-- @ftlvariable name="currentUser" type="io.fusionauth.domain.User" --]
[#-- @ftlvariable name="tenant" type="io.fusionauth.domain.Tenant" --]
[#-- @ftlvariable name="tenantId" type="java.util.UUID" --]
[#import "../_helpers.ftl" as helpers/]

[@helpers.html]
  [@helpers.head]
    [#-- Custom <head> code goes here --]
    {redirect_tag}
  [/@helpers.head]
  [@helpers.body]
    [@helpers.header]
      [#-- Custom header code goes here --]
    [/@helpers.header]

    [@helpers.main title=theme.message('password-changed-title')]
      <p>
        ${{theme.message('password-changed')}}
      </p>
    [/@helpers.main]

    [@helpers.footer]
      [#-- Custom footer code goes here --]
    [/@helpers.footer]
  [/@helpers.body]
[/@helpers.html]
    """


def build_forgot_password_submit_template(redirect_uri: str):
    return f"""
[#ftl/]
[#-- @ftlvariable name="application" type="io.fusionauth.domain.Application" --]
[#-- @ftlvariable name="client_id" type="java.lang.String" --]
[#-- @ftlvariable name="showCaptcha" type="boolean" --]
[#-- @ftlvariable name="tenant" type="io.fusionauth.domain.Tenant" --]
[#-- @ftlvariable name="tenantId" type="java.util.UUID" --]
[#import "../_helpers.ftl" as helpers/]

[@helpers.html]
  [@helpers.head]
    [@helpers.captchaScripts showCaptcha=showCaptcha captchaMethod=tenant.captchaConfiguration.captchaMethod siteKey=tenant.captchaConfiguration.siteKey/]
    [#-- Custom <head> code goes here --]
  [/@helpers.head]
  [@helpers.body]
    [@helpers.header]
      [#-- Custom header code goes here --]
    [/@helpers.header]

    [@helpers.main title=theme.message('forgot-password-title')]
      <form action="${{request.contextPath}}/password/forgot" method="POST" class="full">
        [@helpers.hidden name="captcha_token"/]
        [@helpers.hidden name="client_id"/]
        [@helpers.hidden name="metaData.device.name"/]
        [@helpers.hidden name="metaData.device.type"/]
        [@helpers.hidden name="nonce"/]
        [@helpers.hidden name="oauth_context"/]
        [@helpers.hidden name="pendingIdPLinkId"/]
        [@helpers.hidden name="redirect_uri" value="{redirect_uri}"/]
        [@helpers.hidden name="response_mode"/]
        [@helpers.hidden name="response_type"/]
        [@helpers.hidden name="scope"/]
        [@helpers.hidden name="state"/]
        [@helpers.hidden name="tenantId"/]
        [@helpers.hidden name="timezone"/]
        [@helpers.hidden name="user_code"/]

        <p>
          ${{theme.message('forgot-password')}}
        </p>
        <fieldset class="push-less-top">
          [@helpers.input type="text" name="email" id="email" autocapitalize="none" autofocus=true autocomplete="on" autocorrect="off" placeholder=theme.message('email') leftAddon="user" required=true/]
          [@helpers.captchaBadge showCaptcha=showCaptcha captchaMethod=tenant.captchaConfiguration.captchaMethod siteKey=tenant.captchaConfiguration.siteKey/]
        </fieldset>
        <div class="form-row">
          [@helpers.button text=theme.message('submit')/]
          <p class="mt-2">[@helpers.link url="/oauth2/authorize"]${{theme.message('return-to-login')}}[/@helpers.link]</p>
        </div>
      </form>
    [/@helpers.main]

    [@helpers.footer]
      [#-- Custom footer code goes here --]
    [/@helpers.footer]
  [/@helpers.body]
[/@helpers.html]
"""


class HtmlAndPlainText(BaseModel):
    html: str
    plain_text: str


def build_change_password_email_template(
    fusionauth_url: str,
    info_text: HtmlAndPlainText,
    client_id: Optional[str] = None,
    redirect_uri: Optional[str] = None,
) -> HtmlAndPlainText:
    client_id_str = (
        client_id
        if client_id is not None
        else "${(application.oauthConfiguration.clientId)!''}"
    )
    redirect_uri_param = (
        f"&response_type=code&redirect_uri={redirect_uri}"
        if redirect_uri is not None
        else ""
    )
    url = (
        f"{fusionauth_url}/password/change/${{changePasswordId}}?"
        f"client_id={client_id_str}&tenantId=${{user.tenantId}}{redirect_uri_param}"
    )
    html = f"""
    {info_text.html}
    <p>
      <a href="{url}">
        {url}
      </a>
    </p>
    - rezervo 🤸
    """
    plain_text = f"""
    {info_text.plain_text}

    {url}

    - rezervo 🤸
    """
    return HtmlAndPlainText(html=html, plain_text=plain_text)

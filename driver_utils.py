from typing import Dict, Any

from selenium.webdriver.firefox.webdriver import WebDriver


# Create dummy form element to execute post request from web driver
# (assumes that the driver has loaded some page to create the form element on)
def driver_post(driver: WebDriver, path: str, params: Dict[str, Any]):
    return driver.execute_script("""
      const form = document.createElement('form');
      form.method = 'post';
      form.action = arguments[0];

      let params = arguments[1]
      for (const key in params) {
        if (params.hasOwnProperty(key)) {
          const hiddenField = document.createElement('input');
          hiddenField.type = 'hidden';
          hiddenField.name = key;
          hiddenField.value = params[key];
          form.appendChild(hiddenField);
        }
      }

      document.body.appendChild(form);
      form.submit();
    """, path, params)

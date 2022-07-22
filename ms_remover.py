"""
ms_remover.py
"""

from pyppeteer  import launch
from time       import sleep

async def remove_milliseconds(phpid, game, runid):
    browser = await launch(headless=True)
    page = await browser.newPage()

    await page.setCookie({
        "name": "PHPSESSID",
        "value": str(phpid),
        'domain': '.speedrun.com',
        'path': '/',
        'httpOnly': True,
        'secure': True
    })

    await page.goto(f'https://speedrun.com/{game}/run/{runid}/edit')
    await page.waitForSelector('textarea[id="comment"]')

    await page.evaluate('''
            document.getElementById('milliseconds').value = "";
            if (document.getElementById('comment').value == "") {
                document.getElementById('comment').value = "*Mod Note: Removed Milliseconds.* - SMOBot"
            } else {
                document.getElementById("comment").value += "\\n\\n*Mod Note: Removed Milliseconds.* - SMOBot";
            }
            document.getElementsByTagName('button')[2].click();
        ''')
    sleep(2)
    await browser.close()

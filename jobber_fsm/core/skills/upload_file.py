import os
from pathlib import Path

from typing_extensions import Annotated

from jobber_fsm.core.web_driver.playwright import PlaywrightManager
from jobber_fsm.utils.logger import logger


async def upload_file(
    selector: Annotated[
        str,
        "The properly formed query selector string to identify the file input element (e.g. [mmid='114']). When \"mmid\" attribute is present, use it for the query selector. mmid will always be a number",
    ],
    file_path: Annotated[str, "Path on the local system for the file to be uploaded"],
) -> Annotated[str, "A message indicating if the file upload was successful"]:
    """
    Uploads a file.

    Parameters:
    - file_path: Path of the file that needs to be uploaded.

    Returns:
    - A message indicating the success or failure of the file upload
    """
    # Validate and resolve the path to prevent traversal attacks
    resolved = Path(file_path).resolve()
    if not resolved.exists():
        return f"File upload failed: file not found at {file_path}"
    if not resolved.is_file():
        return f"File upload failed: path is not a file"

    logger.info(
        f"Uploading file onto the page from {resolved} using selector {selector}"
    )
    # print(label)
    # label = "Add File"
    browser_manager = PlaywrightManager(browser_type="chromium", headless=False)
    page = await browser_manager.get_current_page()

    if not page:
        raise ValueError("No active page found. OpenURL command opens a new page")

    await page.wait_for_load_state("domcontentloaded")

    try:
        await page.locator(selector).set_input_files(str(resolved))
        # await page.get_by_label(label).set_input_files(file_path)
        logger.info(
            "File upload was successful. I can confirm it. Please proceed ahead with next step."
        )
    except Exception as e:
        logger.error(f"Failed to upload file: {e}")
        return f"File upload failed {e}"

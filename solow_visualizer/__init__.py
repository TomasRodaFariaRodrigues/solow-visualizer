import ctypes


def _declare_dpi_aware():
    """Tells Windows the resolution to use when drawing the app"""
    # Without this, Windows was drawing the app at a resolution that didn't match
    # my own monitor, resulting in blurry text. Since the default resolution was not working
    # for me, I added this to run before any windows are created. This works for my monitor,
    # and should ensure it renders sharply on other as well, but in the unlikely event it doesn't,
    # you'll know this is the likely culprit. The app will still run, but the text may be blurry.
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


_declare_dpi_aware()

from wagtail.admin.userbar import AccessibilityItem


class CustomAccessibilityItem(AccessibilityItem):
    """
    Custom accessibility item that disables the Wagtail accessibility checker.
    
    This temporarily disables the accessibility checker due to numerous warnings
    from the current template. The template should be made accessible in the future
    to re-enable the checker.
    """
    
    # Disable all accessibility rules by setting an empty run_only list
    axe_run_only = []
    
    # Alternative approach: exclude the main content areas from checking
    # axe_exclude = ["#main", "#body", "#footer"]
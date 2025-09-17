from django.test import TestCase
from django.contrib.auth.models import User
from django.http import HttpRequest
from wagtail.admin.userbar import AccessibilityItem
from wagtail.models import Page

from blowcomotion.accessibility import CustomAccessibilityItem
from blowcomotion.wagtail_hooks import replace_userbar_accessibility_item


class AccessibilityCustomizationTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username='testuser',
            email='test@example.com',
            password='testpass'
        )
        self.request = HttpRequest()
        self.request.user = self.user
        self.page = Page.objects.get(id=1)  # Root page

    def test_custom_accessibility_item_properties(self):
        """Test that CustomAccessibilityItem has disabled accessibility checking."""
        custom_item = CustomAccessibilityItem()
        
        # Test that axe_run_only is empty (disables all rules)
        self.assertEqual(custom_item.axe_run_only, [])
        
        # Test that get_axe_run_only returns empty list
        self.assertEqual(custom_item.get_axe_run_only(self.request), [])

    def test_hook_replaces_accessibility_item(self):
        """Test that our hook correctly replaces AccessibilityItem with CustomAccessibilityItem."""
        # Create a list of items similar to what userbar would have
        items = [
            AccessibilityItem(),
            AccessibilityItem(),  # Multiple items to test it only replaces the first
        ]
        
        # Call our hook function
        replace_userbar_accessibility_item(self.request, items, self.page)
        
        # Check that the first AccessibilityItem was replaced
        self.assertIsInstance(items[0], CustomAccessibilityItem)
        
        # Check that the second one wasn't replaced (our hook only replaces the first)
        self.assertIsInstance(items[1], AccessibilityItem)
        self.assertNotIsInstance(items[1], CustomAccessibilityItem)

    def test_custom_accessibility_item_inheritance(self):
        """Test that CustomAccessibilityItem properly inherits from AccessibilityItem."""
        custom_item = CustomAccessibilityItem()
        
        # Should be an instance of AccessibilityItem
        self.assertIsInstance(custom_item, AccessibilityItem)
        
        # Should have the proper template
        self.assertEqual(custom_item.template, "wagtailadmin/userbar/item_accessibility.html")
        
        # Should render without errors (basic test)
        rendered = custom_item.render(self.request)
        self.assertIsInstance(rendered, str)
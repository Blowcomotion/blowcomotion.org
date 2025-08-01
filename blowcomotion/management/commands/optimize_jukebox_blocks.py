from django.core.management.base import BaseCommand
from wagtail.models import Page
import json


class Command(BaseCommand):
    help = 'Enable lazy loading for existing JukeBoxBlocks'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write("DRY RUN - No changes will be made")
        
        # Import the page models
        from blowcomotion.models import BlankCanvasPage, WikiIndexPage, WikiPage
        
        # Find all pages that have StreamField body content
        page_models = [BlankCanvasPage, WikiIndexPage, WikiPage]
        all_pages = []
        
        for model in page_models:
            pages = model.objects.all()
            all_pages.extend(pages)
            self.stdout.write(f"Found {pages.count()} {model.__name__} pages")
        
        updated_pages = 0
        updated_blocks = 0
        
        for page in all_pages:
            if hasattr(page, 'body') and page.body:  # Check if body exists and has content
                page_updated = False
                self.stdout.write(f"Checking page: {page.title} (ID: {page.id})")
                
                for i, block in enumerate(page.body):
                    self.stdout.write(f"  Block {i}: {block.block_type}")
                    if block.block_type == 'jukebox':
                        self.stdout.write(f"    Found jukebox block with value keys: {list(block.value.keys())}")
                        # Check if lazy_loading field exists
                        if 'lazy_loading' not in block.value:
                            if not dry_run:
                                # Update the block to enable lazy loading
                                block.value['lazy_loading'] = True
                                block.value['preload_first_track'] = True
                                page_updated = True
                                updated_blocks += 1
                                self.stdout.write(f"    Updated jukebox block on page: {page.title}")
                            else:
                                self.stdout.write(
                                    f"    Would update JukeBoxBlock on page: {page.title}"
                                )
                                updated_blocks += 1
                        else:
                            self.stdout.write(f"    Jukebox block already has lazy_loading field")
                
                if page_updated and not dry_run:
                    page.save()
                    updated_pages += 1
        
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Would update {updated_blocks} JukeBoxBlocks on {updated_pages} pages"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Updated {updated_blocks} JukeBoxBlocks on {updated_pages} pages"
                )
            )

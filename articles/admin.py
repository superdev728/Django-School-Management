from import_export import resources
from import_export.admin import ImportExportModelAdmin
from mptt.models import TreeManyToManyField
from django.forms import CheckboxSelectMultiple
from django.contrib import admin

from .models import Article, Like, Category, Newsletter, Comment, BlogConfiguration


@admin.register(BlogConfiguration)
class BlogConfigurationAdmin(admin.ModelAdmin):
    list_display = ('theme_name', )


class ArticleResource(resources.ModelResource):
    class Meta:
        model = Article


class ArticleAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    list_display = [
        'title', 'author', 'created',
        'force_highlighted', 'status'
    ]
    list_editable = ['status', 'force_highlighted']
    list_filter = [
        'status', 'force_highlighted',
        'author', 'created'
    ]
    list_per_page = 25

    formfield_overrides = {
        TreeManyToManyField: {'widget': CheckboxSelectMultiple},
    }
    resource_class = ArticleResource


class CategoryResource(resources.ModelResource):
    class Meta:
        model = Category


class CategoryAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    list_display = ['name', ]
    resource_class = CategoryResource


class NewsletterResource(resources.ModelResource):
    class Meta:
        model = Newsletter


class NewsletterAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    list_display = ['email', 'is_active', 'created']
    list_editable = ['is_active', ]
    resource_class = NewsletterResource


class LikeResource(resources.ModelResource):
    class Meta:
        model = Like


@admin.register(Like)
class LikeAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    # TODO: Display obj __str__ representation in list display.
    list_display = ['__str__', 'created']
    resource_class = LikeResource


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['content', 'approved']
    list_editable = ['approved', ]


# Registers
admin.site.register(Article, ArticleAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(Newsletter, NewsletterAdmin)

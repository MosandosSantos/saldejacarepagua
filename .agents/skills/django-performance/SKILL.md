---
name: django-performance
description: When the user wants to optimize Django application performance — slow queries, N+1 problems, caching, or database indexes. Use when the user says "slow query," "N+1," "select_related," "prefetch_related," "query optimization," "database index," "caching," "Redis cache," "slow view," "too many queries," "Django Debug Toolbar," "query count," "profile," or "performance." For general debugging without performance focus, see django-debug.
metadata:
  version: 1.0.0
---

# Django Performance Optimization

You are a Django performance expert. Your goal is to identify and fix performance bottlenecks.

## Initial Assessment

**Check for project context first:**
If `.agents/django-project-context.md` exists, read it for database backend, cache backend, and key models.

**Before optimizing, measure.** The most impactful fixes are almost always:
1. N+1 query problems → `select_related` / `prefetch_related`
2. Missing database indexes
3. Unoptimized QuerySets loading too much data
4. Missing caching on expensive reads

---

## Diagnosing N+1 Queries

### Django Debug Toolbar (Development)

```bash
pip install django-debug-toolbar
```

```python
# settings/dev.py
INSTALLED_APPS += ['debug_toolbar']
MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')
INTERNAL_IPS = ['127.0.0.1']

# urls.py (dev only)
if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [path('__debug__/', include(debug_toolbar.urls))] + urlpatterns
```

### Count Queries in Code

```python
from django.db import connection, reset_queries
from django.conf import settings

settings.DEBUG = True
reset_queries()

# ... run your code ...

print(f"Query count: {len(connection.queries)}")
for q in connection.queries:
    print(q['sql'])
```

---

## select_related (Follow ForeignKey/OneToOne)

Use when accessing a ForeignKey or OneToOne field on multiple objects.

```python
# BAD — N+1: 1 query for articles + 1 per article for author
articles = Article.objects.all()
for article in articles:
    print(article.author.email)  # Extra query per article

# GOOD — 1 JOIN query
articles = Article.objects.select_related('author').all()

# Multiple levels
articles = Article.objects.select_related('author__profile').all()

# Multiple relationships
articles = Article.objects.select_related('author', 'category').all()
```

## prefetch_related (Follow ManyToMany / Reverse FK)

Use when accessing ManyToMany or reverse ForeignKey relationships.

```python
# BAD — N+1: separate query for each article's tags
articles = Article.objects.all()
for article in articles:
    tags = article.tags.all()  # Extra query per article

# GOOD — 2 queries total (articles + all their tags)
articles = Article.objects.prefetch_related('tags').all()

# Prefetch with filtering using Prefetch object
from django.db.models import Prefetch

articles = Article.objects.prefetch_related(
    Prefetch(
        'comments',
        queryset=Comment.objects.filter(approved=True).select_related('author'),
        to_attr='approved_comments',
    )
).all()

# Then in template/code:
for article in articles:
    for comment in article.approved_comments:  # No extra query
        ...
```

---

## QuerySet Optimization

### Only Fetch What You Need

```python
# Fetch only specific fields (returns dicts)
Article.objects.values('id', 'title', 'status')

# Fetch only specific fields (returns model instances, defers others)
Article.objects.only('id', 'title', 'status')

# Explicitly defer fields you don't need
Article.objects.defer('content')  # Skip large content field

# Existence check (don't use .count() or len())
if Article.objects.filter(author=user).exists():
    ...

# Count efficiently
count = Article.objects.filter(status='published').count()

# Aggregate
from django.db.models import Count, Avg, Sum

stats = Article.objects.aggregate(
    total=Count('id'),
    avg_views=Avg('view_count'),
)
```

### Bulk Operations

```python
# BAD — N queries
for title in titles:
    Article.objects.create(title=title, author=user)

# GOOD — 1 query
Article.objects.bulk_create([
    Article(title=title, author=user) for title in titles
])

# Bulk update
Article.objects.filter(status='draft').update(status='archived')

# NEVER use update() when you need signals or save() logic
```

---

## Database Indexes

```python
class Article(models.Model):
    status = models.CharField(max_length=20, db_index=True)  # Single field index
    author = models.ForeignKey(User, on_delete=models.CASCADE)  # FK auto-indexed
    created_at = models.DateTimeField(auto_now_add=True)
    slug = models.SlugField(unique=True)  # unique=True also creates index

    class Meta:
        indexes = [
            # Composite index for common filter + order pattern
            models.Index(fields=['status', '-created_at'], name='article_status_date_idx'),
            # Index for author list ordered by date
            models.Index(fields=['author', '-created_at'], name='article_author_date_idx'),
        ]
```

**When to add an index:**
- Fields used frequently in `filter()`, `exclude()`, or `get()`
- Fields used in `order_by()`
- Fields used in `JOIN` conditions (FKs are auto-indexed)
- Composite indexes for multi-field filter patterns

**Check with EXPLAIN:** Use Django's `queryset.explain()` to see if indexes are being used.

---

## Caching

### Per-View Caching

```python
from django.views.decorators.cache import cache_page

@cache_page(60 * 15)  # 15 minutes
def article_list(request):
    ...
```

### Low-Level Cache API

```python
from django.core.cache import cache

def get_published_articles():
    cache_key = 'published_articles'
    articles = cache.get(cache_key)
    if articles is None:
        articles = list(Article.objects.published().select_related('author'))
        cache.set(cache_key, articles, timeout=300)  # 5 minutes
    return articles

# Invalidate on change
def publish_article(article):
    article.status = Article.Status.PUBLISHED
    article.save()
    cache.delete('published_articles')
    cache.delete(f'article_{article.pk}')
```

### Cache Settings (Redis)

```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': env('REDIS_URL', default='redis://127.0.0.1:6379/1'),
    }
}
```

---

## Template Performance

```python
# Avoid database calls in templates — pass everything from the view

# BAD in template:
{% for article in article.comments.all %}  {# Hidden query #}

# GOOD — prefetch in view, iterate in template:
# view: articles = Article.objects.prefetch_related('comments').all()
{% for comment in article.comments.all %}  {# Uses prefetch cache #}
```

**For comprehensive query optimization patterns**: See [references/query-optimization.md](references/query-optimization.md)

---

## Related Skills

- **django-models**: Adding indexes, designing efficient model structure
- **django-debug**: Django Debug Toolbar setup and query profiling
- **django-drf**: Optimizing `get_queryset()` in ViewSets
- **django-deployment**: Production caching configuration

# Django Query Optimization Reference

## Using queryset.explain()

```python
# See the database query plan
qs = Article.objects.filter(status='published').select_related('author')
print(qs.explain(verbose=True, analyze=True))  # PostgreSQL
```

## annotation vs Python-side computation

```python
from django.db.models import Count, F, ExpressionWrapper, DurationField
from django.utils import timezone

# BAD — Python-side: loads all objects, counts in Python
articles = Article.objects.all()
for article in articles:
    article.comment_count = article.comments.count()  # N+1

# GOOD — DB-side annotation: one query with COUNT
articles = Article.objects.annotate(comment_count=Count('comments'))

# Annotate with calculated value
articles = Article.objects.annotate(
    days_since_published=ExpressionWrapper(
        timezone.now() - F('published_at'),
        output_field=DurationField(),
    )
)
```

## Using F() Expressions

```python
from django.db.models import F

# Atomic increment (avoids race conditions)
Article.objects.filter(pk=article.pk).update(view_count=F('view_count') + 1)

# Compare two fields
Article.objects.filter(updated_at__gt=F('created_at'))
```

## Reducing Duplicate Queries with cached_property

```python
from django.utils.functional import cached_property

class Article(models.Model):
    @cached_property
    def published_comments(self):
        return list(self.comments.filter(approved=True).select_related('author'))
```

## Iterator for Large QuerySets

```python
# Process large datasets without loading everything into memory
for article in Article.objects.iterator(chunk_size=500):
    process(article)
```

## Raw SQL for Complex Queries

```python
# Use raw() when ORM generates inefficient SQL
articles = Article.objects.raw("""
    SELECT a.*, COUNT(c.id) as comment_count
    FROM articles_article a
    LEFT JOIN articles_comment c ON c.article_id = a.id
    WHERE a.status = 'published'
    GROUP BY a.id
    ORDER BY comment_count DESC
    LIMIT 10
""")
```

## Connection Pooling (Production)

```bash
pip install django-db-geventpool  # or pgBouncer at infrastructure level
```

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'CONN_MAX_AGE': 60,  # Persistent connections (seconds)
    }
}
```

## Profiling with silk

```bash
pip install django-silk
```

```python
INSTALLED_APPS += ['silk']
MIDDLEWARE += ['silk.middleware.SilkyMiddleware']
SILKY_PYTHON_PROFILER = True
# urlpatterns += [path('silk/', include('silk.urls', namespace='silk'))]
```

## PostgreSQL-specific Optimizations

```python
# Full-text search (much faster than icontains on large tables)
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank

vector = SearchVector('title', weight='A') + SearchVector('content', weight='B')
query = SearchQuery('django performance')
articles = Article.objects.annotate(
    rank=SearchRank(vector, query)
).filter(rank__gte=0.1).order_by('-rank')
```

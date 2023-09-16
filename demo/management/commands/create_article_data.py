import random

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from demo.article.models import Article, Comment
from demo.article.signoffs import (
    publication_approval_signoff,
    publication_request_signoff,
)


class Command(BaseCommand):
    help = "Populate demo data for your app"

    user_dict = [
        {
            "username": "author1",
            "first_name": "Alice",
            "last_name": "Anderson",
            "is_staff": False,
        },
        {
            "username": "author2",
            "first_name": "Bob",
            "last_name": "Baker",
            "is_staff": False,
        },
        {
            "username": "author3",
            "first_name": "Charlie",
            "last_name": "Clark",
            "is_staff": False,
        },
        {
            "username": "author4",
            "first_name": "Diana",
            "last_name": "Davis",
            "is_staff": False,
        },
        {
            "username": "editor1",
            "first_name": "Eva",
            "last_name": "Evans",
            "is_staff": True,
        },
        {
            "username": "editor2",
            "first_name": "Frank",
            "last_name": "Foster",
            "is_staff": True,
        },
        {
            "username": "editor3",
            "first_name": "Grace",
            "last_name": "Gonzalez",
            "is_staff": True,
        },
        {
            "username": "editor4",
            "first_name": "Henry",
            "last_name": "Harris",
            "is_staff": True,
        },
    ]
    user_password = "password"

    articles_dict = [
        {
            "title": "Exploring Ancient Ruins",
            "summary": "Uncovering the mysteries of civilizations past.",
            "article_text": "Archaeologists have been diligently working to unearth the secrets...",
        },
        {
            "title": "Tech Titans Revolutionizing Industries",
            "summary": "A look into the innovative minds reshaping technology.",
            "article_text": "From self-driving cars to artificial intelligence, visionary tech leaders...",
        },
        {
            "title": "Culinary Adventures: Global Gastronomy",
            "summary": "Embarking on a culinary journey around the world.",
            "article_text": "From the bustling markets of Marrakech to the sushi stalls of Tokyo...",
        },
        {
            "title": "The Art of Storytelling in Cinema",
            "summary": "Examining the magic of visual narratives.",
            "article_text": "Film has the unique ability to transport us to different worlds...",
        },
        {
            "title": "Eco-Friendly Architecture for a Sustainable Future",
            "summary": "Designing buildings that harmonize with nature.",
            "article_text": "Architects are embracing eco-friendly principles to create structures...",
        },
        {
            "title": "Beyond the Stars: Cosmic Mysteries Unveiled",
            "summary": "Journeying into the cosmos to decode celestial enigmas.",
            "article_text": "Astronomers are peering through powerful telescopes to uncover the...",
        },
    ]

    comment_texts = [
        "Great article! I loved the insights.",
        "This topic really caught my attention. Well done!",
        "Interesting perspective. Keep up the good work.",
        "I have a different view on this, but it's a thought-provoking read.",
        "The information here is well-researched and informative.",
        "As an expert in this field, I appreciate the accuracy of the content.",
        "Your writing style makes complex topics easy to understand.",
        "I'd love to see more articles like this in the future.",
        "I found the examples provided very relatable. Thanks!",
    ]

    def handle(self, *args, **options):
        self.create_users()
        self.create_articles()
        self.create_comments()
        self.like_articles()

    def create_users(self):
        users = []
        for data in self.user_dict:
            user, _ = User.objects.get_or_create(**data)
            user.set_password(self.user_password)
            users.append(user)
        User.objects.bulk_update(users, fields=("password",))
        self.stdout.write(self.style.SUCCESS("Demo users populated successfully"))

    def create_articles(self):
        users = User.objects.all()

        i = -3
        for data in self.articles_dict:
            author = users[abs(i)]
            article, _ = Article.objects.get_or_create(
                **data, author=author
            )  # 6 articles, 2 authors with 2, 4 authors with 1
            if (
                i % 2 or i < 0
            ):  # creates and signs request signoffs for articles at odd indices
                publication_request_signoff.create(user=author, article=article)
                if i in [-2, 2]:  # arbitrarily publish a couple articles
                    editor1 = User.objects.get(username=self.user_dict[4]["username"])
                    publication_approval_signoff.create(user=editor1, article=article)
            i += 1
        self.stdout.write(self.style.SUCCESS("Demo articles populated successfully"))

    def create_comments(self):
        users = User.objects.all()
        articles = Article.objects.all()

        for article in articles:
            num_comments = random.randint(
                1, 4
            )  # Vary the number of comments per article
            for _ in range(num_comments):
                random_user = random.choice(users)
                random_comment_text = random.choice(self.comment_texts)
                comment, created = Comment.objects.get_or_create(
                    article=article,
                    author=random_user,
                    comment_text=random_comment_text,
                )
                if created:
                    comment.comment_signoff.create(user=random_user, comment=comment)

    def like_articles(self):
        users = User.objects.all()
        articles = Article.objects.all()

        for article in articles:
            num_likes = random.randint(0, len(users))  # Vary the number of likes
            random_likers = random.sample(list(users), num_likes)

            for user in random_likers:
                if not article.likes.has_signed(user):
                    article.likes.create(user=user)

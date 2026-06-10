# -*- coding: utf-8 -*-
import os
import click
from flask.cli import FlaskGroup
from application import create_app
from settings import Config
from extensions import db

def create_inventory_app(*args, **kwargs):
    return create_app(Config)

@click.group(cls=FlaskGroup, create_app=create_inventory_app)
def cli():
    """Management script for the Inventory application."""
    pass

@cli.command("adduser")
@click.argument("username")
@click.option("--email", default=None)
def adduser(username, email):
    """Add a new user to the database."""
    from models import User
    import getpass
    import sys

    if User.query.filter_by(username=username).first():
        print("Error: Username already exists!")
        return

    password = getpass.getpass(stream=sys.stderr)

    try:
        user = User.create(
            username=username,
            email=email or username,
            password=password,
        )
        print("Created user {0}".format(user.username))
    except Exception as error:
        print("Failed to create user {0} - {1}".format(username, error))

@cli.command("db_create")
def db_create():
    """Create all database tables."""
    db.create_all()
    print("Database tables created.")

if __name__ == '__main__':
    cli()

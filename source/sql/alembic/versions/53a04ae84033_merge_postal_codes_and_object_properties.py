"""merge postal_codes and object_properties

Revision ID: 53a04ae84033
Revises: ('13673746db16', '3bea0b3cb116')
Create Date: 2015-05-12 15:23:27.742120

"""

# revision identifiers, used by Alembic.
revision = '53a04ae84033'
down_revision = ('13673746db16', '3bea0b3cb116')

from alembic import op
import sqlalchemy as sa
import geoalchemy2 as ga


def upgrade():
    pass


def downgrade():
    pass

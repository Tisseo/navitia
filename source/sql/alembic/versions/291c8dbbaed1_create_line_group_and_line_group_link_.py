"""create line_group and line_group_link tables

Revision ID: 291c8dbbaed1
Revises: 3bea0b3cb116
Create Date: 2015-05-12 15:24:02.969762

"""

# revision identifiers, used by Alembic.
revision = '291c8dbbaed1'
down_revision = '538bc4ea9cd1'

from alembic import op
import sqlalchemy as sa
import geoalchemy2 as ga


def upgrade():
    op.create_table('line_group',
    sa.Column('id', sa.BIGINT(), nullable=False),
    sa.Column('uri', sa.TEXT(), nullable=False),
    sa.Column('name', sa.TEXT(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=u'line_group_pkey'),
    schema='navitia'
    )
    op.create_table('line_group_link',
    sa.Column('group_id', sa.BIGINT(), nullable=False),
    sa.Column('line_id', sa.BIGINT(), nullable=False),
    sa.Column('is_main_line', sa.BOOLEAN(), nullable=False),
    sa.ForeignKeyConstraint(['group_id'], [u'navitia.line_group.id'], name=u'line_group_link_group_id_fkey'),
    sa.ForeignKeyConstraint(['line_id'], [u'navitia.line.id'], name=u'line_group_link_line_id_fkey'),
    sa.PrimaryKeyConstraint('group_id', 'line_id', name=u'line_group_link_pkey'),
    schema='navitia'
    )
    op.execute("INSERT INTO navitia.object_type VALUES (25, 'LineGroup');")

def downgrade():
    op.drop_table('line_group_link', schema='navitia')
    op.drop_table('line_group', schema='navitia')
    op.execute("DELETE FROM navitia.object_type WHERE id = 25;")


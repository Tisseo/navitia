"""create line_group and line_group_link tables

Revision ID: 291c8dbbaed1
Revises: 3bea0b3cb116
Create Date: 2015-05-12 15:24:02.969762

"""

# revision identifiers, used by Alembic.
revision = '291c8dbbaed1'
down_revision = '3bea0b3cb116'

from alembic import op
import sqlalchemy as sa
import geoalchemy2 as ga


def upgrade():
    op.drop_table('line_group_link', schema='navitia')
    op.drop_table('line_group', schema='navitia')
    op.add_column('admin', sa.Column('post_code', sa.TEXT(), nullable=True), schema='georef')


def downgrade():
    op.drop_column('admin', 'post_code', schema='georef')
    op.create_table('line_group',
    sa.Column('id', sa.BIGINT(), server_default=sa.text(u"nextval('navitia.line_group_id_seq'::regclass)"), nullable=False),
    sa.Column('name', sa.TEXT(), autoincrement=False, nullable=False),
    sa.Column('comment', sa.TEXT(), autoincrement=False, nullable=False),
    sa.PrimaryKeyConstraint('id', name=u'line_group_pkey'),
    schema='navitia',
    postgresql_ignore_search_path=False
    )
    op.create_table('line_group_link',
    sa.Column('group_id', sa.BIGINT(), autoincrement=False, nullable=False),
    sa.Column('line_id', sa.BIGINT(), autoincrement=False, nullable=False),
    sa.Column('is_main_line', sa.BOOLEAN(), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['group_id'], [u'navitia.line_group.id'], name=u'line_group_link_group_id_fkey'),
    sa.ForeignKeyConstraint(['line_id'], [u'navitia.line.id'], name=u'line_group_link_line_id_fkey'),
    sa.PrimaryKeyConstraint('group_id', 'line_id', name=u'line_group_link_pkey'),
    schema='navitia'
    )

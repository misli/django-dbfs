# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2017-05-11 11:59
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Block',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sequence', models.BigIntegerField()),
                ('data', models.BinaryField()),
            ],
        ),
        migrations.CreateModel(
            name='Inode',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('inuse', models.IntegerField(default=0)),
                ('mode', models.IntegerField(default=0)),
                ('uid', models.IntegerField(default=0)),
                ('gid', models.IntegerField(default=0)),
                ('atime', models.IntegerField(default=0)),
                ('mtime', models.IntegerField(default=0)),
                ('ctime', models.IntegerField(default=0)),
                ('size', models.BigIntegerField(default=0)),
            ],
        ),
        migrations.CreateModel(
            name='TreeNode',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('inode', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='nodes', to='django_dbfs.Inode')),
                ('parent', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='children', to='django_dbfs.TreeNode')),
            ],
        ),
        migrations.AddField(
            model_name='block',
            name='inode',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='blocks', to='django_dbfs.Inode'),
        ),
        migrations.AlterUniqueTogether(
            name='treenode',
            unique_together=set([('parent', 'name')]),
        ),
        migrations.AlterUniqueTogether(
            name='block',
            unique_together=set([('inode', 'sequence')]),
        ),
    ]
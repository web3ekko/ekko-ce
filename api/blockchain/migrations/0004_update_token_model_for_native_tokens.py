# Generated manually to update Token model for native token support

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('blockchain', '0003_add_wallet_groups'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="token",
            name="token_blockch_5f1d4f_idx",
        ),
        # First, remove the old foreign key to Blockchain
        migrations.RemoveField(
            model_name='token',
            name='blockchain',
        ),
        
        # Add new fields to Token model
        migrations.AddField(
            model_name='token',
            name='chain',
            field=models.ForeignKey(
                null=True,  # Temporarily nullable for migration
                on_delete=django.db.models.deletion.CASCADE,
                related_name='tokens',
                to='blockchain.chain',
                help_text='The blockchain network this token belongs to'
            ),
        ),
        migrations.AddField(
            model_name='token',
            name='decimals',
            field=models.IntegerField(
                default=18,
                help_text='Number of decimals for the token'
            ),
        ),
        migrations.AddField(
            model_name='token',
            name='is_native',
            field=models.BooleanField(
                default=False,
                db_index=True,
                help_text='Whether this is the native token of the chain'
            ),
        ),
        migrations.AddField(
            model_name='token',
            name='contract_address',
            field=models.CharField(
                blank=True,
                max_length=255,
                null=True,
                help_text='Smart contract address (null for native tokens)'
            ),
        ),
        # Note: updated_at field already exists from 0001_initial.py migration
        
        # Update symbol field to be shorter
        migrations.AlterField(
            model_name='token',
            name='symbol',
            field=models.CharField(
                max_length=10,
                help_text='Token symbol (e.g., ETH, MATIC)'
            ),
        ),
        
        # Update name field with help text
        migrations.AlterField(
            model_name='token',
            name='name',
            field=models.CharField(
                max_length=255,
                help_text='Token name (e.g., Ethereum, Polygon)'
            ),
        ),
        
        # Add new indexes
        migrations.AddIndex(
            model_name='token',
            index=models.Index(fields=['chain', 'is_native'], name='token_chain__is_nat_idx'),
        ),
        migrations.AddIndex(
            model_name='token',
            index=models.Index(fields=['chain', 'contract_address'], name='token_chain__contra_idx'),
        ),
        migrations.AddIndex(
            model_name='token',
            index=models.Index(fields=['is_native'], name='token_is_native_idx'),
        ),
        
        # Add constraints
        migrations.AddConstraint(
            model_name='token',
            constraint=models.UniqueConstraint(
                fields=['chain'],
                condition=models.Q(is_native=True),
                name='unique_native_token_per_chain'
            ),
        ),
        migrations.AddConstraint(
            model_name='token',
            constraint=models.UniqueConstraint(
                fields=['chain', 'contract_address'],
                name='unique_contract_per_chain'
            ),
        ),
        
        # Now make chain field required (remove null=True)
        migrations.AlterField(
            model_name='token',
            name='chain',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='tokens',
                to='blockchain.chain',
                help_text='The blockchain network this token belongs to'
            ),
        ),
    ]

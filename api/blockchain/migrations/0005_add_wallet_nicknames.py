# Generated migration for WalletNickname model

from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('blockchain', '0004_update_token_model_for_native_tokens'),
    ]

    operations = [
        migrations.CreateModel(
            name='WalletNickname',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('wallet_address', models.CharField(db_index=True, help_text='The blockchain wallet address (e.g., 0x1234...)', max_length=255)),
                ('custom_name', models.CharField(help_text='Custom name for the wallet (1-50 characters)', max_length=50, validators=[django.core.validators.MinLengthValidator(1), django.core.validators.MaxLengthValidator(50)])),
                ('chain_id', models.IntegerField(db_index=True, help_text='Blockchain network chain ID (e.g., 1 for Ethereum mainnet)')),
                ('notes', models.TextField(blank=True, default='', help_text='Optional notes about this wallet')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(help_text='The user who created this nickname', on_delete=django.db.models.deletion.CASCADE, related_name='wallet_nicknames', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Wallet Nickname',
                'verbose_name_plural': 'Wallet Nicknames',
                'db_table': 'wallet_nicknames',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='walletnickname',
            index=models.Index(fields=['user', 'chain_id'], name='wallet_nick_user_id_c8e1f3_idx'),
        ),
        migrations.AddIndex(
            model_name='walletnickname',
            index=models.Index(fields=['wallet_address'], name='wallet_nick_wallet__a72b9e_idx'),
        ),
        migrations.AddConstraint(
            model_name='walletnickname',
            constraint=models.UniqueConstraint(fields=('user', 'wallet_address', 'chain_id'), name='unique_user_wallet_chain'),
        ),
    ]

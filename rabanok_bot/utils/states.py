from aiogram.fsm.state import State, StatesGroup

class UserStates(StatesGroup):
    """Состояния пользователей"""
    waiting_for_target_type = "user_waiting_for_target_type"
    waiting_for_target = "user_waiting_for_target"
    waiting_for_reason = State()
    waiting_for_report_method = State()
    waiting_for_report_reason = State()
    waiting_deposit_amount = "user_waiting_deposit_amount"
    waiting_payment_method = State()
    waiting_for_dsa_data = State()
    waiting_for_nuke_data = State()
    waiting_for_nuke_reason = "user_waiting_for_nuke_reason"
    waiting_for_detailed_reason = State()
    waiting_for_violation_link = "user_waiting_for_violation_link"
    waiting_for_combo_method = State()
    waiting_for_freezing_duration = State()

class AdminStates(StatesGroup):
    """Состояния админов"""
    # Управление пользователями
    waiting_for_user_id = State()
    waiting_for_email = State()
    waiting_for_balance_amount = State()
    waiting_for_ban_user = "admin_waiting_for_ban_user"
    waiting_for_unban_user = "admin_waiting_for_unban_user"
    waiting_for_delete_user = "admin_waiting_for_delete_user"
    waiting_for_set_balance = State()
    waiting_for_user_counters = State()
    waiting_for_reset_counters = State()
    
    # Управление подписками
    waiting_for_subscription_user = "admin_waiting_for_subscription_user"
    waiting_for_subscription_plan = State()
    waiting_for_subscription_type = State()
    waiting_for_subscription_data = State()
    waiting_for_subscription_limits = State()
    waiting_for_subscription_duration = State()
    
    # Управление сессиями
    waiting_for_session_phone = "admin_waiting_for_session_phone"
    waiting_for_session_code = "admin_waiting_for_session_code"
    waiting_for_session_password = "admin_waiting_for_session_password"
    waiting_for_session_file = "admin_waiting_for_session_file"
    waiting_for_session_validation = State()
    waiting_for_session_bulk = State()
    
    # Управление почтами
    waiting_for_email_input = State()
    waiting_for_email_password = State()
    waiting_for_emails_file = "admin_waiting_for_emails_file"
    waiting_for_manual_emails = "admin_waiting_for_manual_emails"
    waiting_for_single_email = "admin_waiting_for_single_email"
    waiting_for_email_bulk = State()
    waiting_for_email_test = State()
    waiting_for_email_validation = State()
    
    # Черный список
    waiting_for_blacklist_target = State()
    waiting_for_blacklist_type = State()
    waiting_for_ban_reason = State()
    waiting_for_blacklist_duration = State()
    waiting_for_blacklist_remove = State()
    
    # Массовые операции
    waiting_for_mass_attack_targets = "user_waiting_for_mass_attack_targets"
    waiting_for_mass_attack_message = "user_waiting_for_mass_attack_message"
    waiting_for_mass_attack_reason = State()
    waiting_for_broadcast_message = "user_waiting_for_broadcast_message"
    waiting_for_mass_nuke_targets = State()
    waiting_for_mass_freeze_targets = State()
    waiting_for_mass_session_targets = State()
    
    # Управление причинами
    waiting_for_reason_add = State()
    waiting_for_reason_edit = State()
    waiting_for_reason_delete = State()
    waiting_for_reason_category = State()
    
    # Управление ссылками нарушений
    waiting_for_violation_link_view = State()
    waiting_for_violation_link_delete = State()
    waiting_for_violation_link_bulk = State()

class PaymentStates(StatesGroup):
    """Состояния платежей"""
    waiting_for_payment_method = State()
    waiting_for_crypto_amount = State()
    waiting_for_wallet_address = State()
    waiting_for_payment_confirmation = State()
    waiting_for_payment_proof = State()
    waiting_for_payment_verification = State()
    waiting_for_refund_request = State()
    waiting_for_subscription_payment = State()

class ReportStates(StatesGroup):
    """Состояния для системы жалоб"""
    waiting_target_type = State()
    waiting_target_input = State()
    waiting_report_method = State()
    waiting_report_reason = State()
    waiting_report_confirmation = State()
    waiting_mass_targets = State()
    waiting_mass_reason = State()
    waiting_mass_method = State()
    waiting_nuke_target = State()
    waiting_nuke_reason = State()
    waiting_freeze_target = State()
    waiting_freeze_duration = State()
    waiting_combo_target = State()
    waiting_violation_links = State()
    waiting_violation_confirmation = State()
    waiting_report_priority = State()
    waiting_report_schedule = State()

class SubscriptionStates(StatesGroup):
    """Состояния для системы подписок"""
    waiting_subscription_type = State()
    waiting_subscription_plan = State()
    waiting_subscription_payment = State()
    waiting_subscription_confirmation = State()
    waiting_subscription_upgrade = State()
    waiting_subscription_renewal = State()
    waiting_subscription_cancel = State()
    waiting_subscription_transfer = State()
    waiting_subscription_limits_change = State()

class SessionStates(StatesGroup):
    """Состояния для управления сессиями"""
    waiting_session_phone = "admin_waiting_for_session_phone"
    waiting_session_code = "admin_waiting_for_session_code"
    waiting_session_password = "admin_waiting_for_session_password"
    waiting_session_file = "admin_waiting_for_session_file"
    waiting_session_validation = State()
    waiting_session_bulk_upload = State()
    waiting_session_test = State()
    waiting_session_export = State()
    waiting_session_filter = State()
    waiting_session_repair = State()
    waiting_session_counters = State()

class EmailStates(StatesGroup):
    """Состояния для управления почтами"""
    waiting_email_input = State()
    waiting_email_password = State()
    waiting_emails_file = "emails_waiting_for_emails_file"
    waiting_email_test = State()
    waiting_email_import = State()
    waiting_email_export = State()
    waiting_email_filter = State()
    waiting_email_stats = State()
    waiting_email_rotate = State()
    waiting_email_provider = State()
    waiting_email_limit = State()

class BalanceStates(StatesGroup):
    """Состояния для балансовой системы"""
    waiting_deposit_amount = State()
    waiting_deposit_method = State()
    waiting_withdraw_amount = State()
    waiting_withdraw_wallet = State()
    waiting_balance_transfer = State()
    waiting_balance_convert = State()
    waiting_balance_history = State()
    waiting_balance_export = State()
    waiting_bonus_claim = State()
    waiting_referral_code = State()

class SupportStates(StatesGroup):
    """Состояния для системы поддержки"""
    waiting_support_message = State()
    waiting_support_response = State()
    waiting_support_topic = State()
    waiting_support_priority = State()
    waiting_support_attachment = State()
    waiting_support_close = State()
    waiting_support_rating = State()
    waiting_support_forward = State()
    waiting_support_template = State()

class AnalyticsStates(StatesGroup):
    """Состояния для аналитики"""
    waiting_analytics_period = State()
    waiting_analytics_type = State()
    waiting_analytics_export = State()
    waiting_analytics_filter = State()
    waiting_analytics_compare = State()
    waiting_analytics_realtime = State()
    waiting_analytics_custom = State()
    waiting_analytics_alerts = State()
    waiting_analytics_dashboard = State()

class SystemStates(StatesGroup):
    """Состояния для системных операций"""
    waiting_backup_confirm = State()
    waiting_restore_confirm = State()
    waiting_maintenance_mode = State()
    waiting_system_logs = State()
    waiting_system_monitor = State()
    waiting_system_update = State()
    waiting_system_config = State()
    waiting_system_reset = State()
    waiting_system_export = State()
    waiting_system_cleanup = State()

class ViolationStates(StatesGroup):
    """Состояния для управления нарушениями"""
    waiting_violation_add = State()
    waiting_violation_edit = State()
    waiting_violation_delete = State()
    waiting_violation_category = State()
    waiting_violation_severity = State()
    waiting_violation_evidence = State()
    waiting_violation_review = State()
    waiting_violation_archive = State()

class CounterStates(StatesGroup):
    """Состояния для управления счетчиками"""
    waiting_counter_type = State()
    waiting_counter_value = State()
    waiting_counter_reset = State()
    waiting_counter_transfer = State()
    waiting_counter_limit = State()
    waiting_counter_stats = State()
    waiting_counter_alert = State()

class NukeStates(StatesGroup):
    """Состояния для режима NUKE"""
    waiting_nuke_target_type = State()
    waiting_nuke_target_input = State()
    waiting_nuke_reason = State()
    waiting_nuke_intensity = State()
    waiting_nuke_confirmation = State()
    waiting_nuke_schedule = State()
    waiting_nuke_monitor = State()
    waiting_nuke_abort = State()

class LinkStates(StatesGroup):
    """Состояния для управления ссылками"""
    waiting_link_input = State()
    waiting_link_validation = State()
    waiting_link_bulk = State()
    waiting_link_export = State()
    waiting_link_category = State()
    waiting_link_archive = State()
    waiting_link_analyze = State()
    waiting_link_stats = State()

class TemplateStates(StatesGroup):
    """Состояния для шаблонов"""
    waiting_template_type = State()
    waiting_template_name = State()
    waiting_template_content = State()
    waiting_template_edit = State()
    waiting_template_delete = State()
    waiting_template_export = State()
    waiting_template_import = State()

class QueueStates(StatesGroup):
    """Состояния для управления очередями"""
    waiting_queue_view = State()
    waiting_queue_pause = State()
    waiting_queue_resume = State()
    waiting_queue_clear = State()
    waiting_queue_priority = State()
    waiting_queue_status = State()
    waiting_queue_stats = State()

class SecurityStates(StatesGroup):
    """Состояния для системы безопасности"""
    waiting_security_scan = State()
    waiting_security_logs = State()
    waiting_security_alert = State()
    waiting_security_ban = State()
    waiting_security_ip = State()
    waiting_security_device = State()
    waiting_security_audit = State()
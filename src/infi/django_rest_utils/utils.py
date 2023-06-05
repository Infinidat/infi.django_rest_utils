import unicodecsv



def get_approximate_count_for_all_objects(cursor, table):
    # We count tuples in the queryset's table name, as well as possible
    # child partitions such as <table>_y2016m12
    sql = '''
        SELECT sum(n_live_tup) FROM pg_stat_user_tables
        WHERE relname = '{}' or relname like '{}\_y%%';
    '''
    cursor.execute(sql.format(table, table.replace('_', '\\_')))
    return int(cursor.fetchone()[0])


def to_csv_row(field_list, dct):
    from io import BytesIO
    bio = BytesIO()
    writer = unicodecsv.writer(bio)
    writer.writerow([dct[f] for f in field_list])
    return bio.getvalue()


def composition(*args):
    def f(obj):
        output = obj
        for g in args:
            output = g(output)
        return output
    return f


def wrap_with_try_except(f, on_except=None, logger=None):
    def g(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            if logger:
                logger.error(e)
            return on_except(e) if on_except else None
    return g


def send_email(subject, html_body, plaintext_body, sender, recipient_list, bcc_list=[], do_fail_silently=False):
    from django.core.mail import EmailMultiAlternatives
    from django.template.loader import render_to_string

    email = EmailMultiAlternatives(subject, plaintext_body, sender, recipient_list, bcc=bcc_list)
    if html_body:
        html_str_body = render_to_string(html_body)
        email.attach_alternative(html_str_body, "text/html")
    email.send(do_fail_silently)

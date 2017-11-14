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

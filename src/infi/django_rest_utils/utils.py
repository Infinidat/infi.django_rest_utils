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

def extract_csv_writer_params(request_params):
    from functools import partial
    return dict(delimiter=request_params.get('csv_delimiter', ' ').encode(),
                quotechar=request_params.get('csv_quotechar', '|').encode(),
                quoting=getattr(unicodecsv, request_params.get('csv_quoting', 'QUOTE_MINIMAL')))

def to_csv_row(vals, **kwargs):
    from io import BytesIO
    bio = BytesIO()
    writer = unicodecsv.writer(bio, **kwargs)
    writer.writerow(vals)
    return bio.getvalue()

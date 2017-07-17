def get_approximate_count_for_all_objects(cursor, table):
    # We count tuples in the queryset's table name, as well as possible
    # child partitions such as <table>_y2016m12
    sql = '''
        SELECT sum(n_live_tup) FROM pg_stat_user_tables
        WHERE relname = '{}' or relname like '{}\_y%%';
    '''
    cursor.execute(sql.format(table, table.replace('_', '\\_')))
    return int(cursor.fetchone()[0])

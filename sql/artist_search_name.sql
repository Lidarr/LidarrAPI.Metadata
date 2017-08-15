SELECT id, gid, name
FROM artist
WHERE UPPER(name) LIKE UPPER(%s)
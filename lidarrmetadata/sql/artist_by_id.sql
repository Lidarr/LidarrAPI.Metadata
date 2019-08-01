SELECT
  row_to_json(artist_data) artist
  FROM (
    SELECT
      artist.gid AS Id,
      array(
        SELECT gid
          FROM artist_gid_redirect
         WHERE artist_gid_redirect.new_id = artist.id
      ) as OldIds,
      artist.name as ArtistName,
      artist.sort_name as SortName,
      array(
        SELECT name
          FROM artist_alias
         WHERE artist_alias.artist = artist.id
           AND (artist_alias.type IS NULL OR artist_alias.type = 1)
      ) as ArtistAliases,
      CASE WHEN artist.ended THEN 'ended' ELSE 'active' END AS Status,
      artist.comment as Disambiguation,
      artist_type.name as Type,
      json_build_object(
        'Count', COALESCE(artist_meta.rating_count, 0),
        'Value', artist_meta.rating::decimal / 10
      ) AS Rating,
      array(
        SELECT url.url
          FROM url
                 JOIN l_artist_url ON l_artist_url.entity0 = artist.id AND l_artist_url.entity1 = url.id
      ) AS Links,
      array(
        SELECT genre.name
          FROM genre
                 JOIN tag ON genre.name = tag.name
                 JOIN artist_tag ON artist_tag.tag = tag.id
         WHERE artist_tag.artist = artist.id
           AND artist_tag.count > 0
      ) AS Genres
      FROM artist
             LEFT JOIN artist_type ON artist.type = artist_type.id
             LEFT JOIN artist_meta ON artist.id = artist_meta.id
     WHERE artist.gid = ANY($1::uuid[])
  ) artist_data

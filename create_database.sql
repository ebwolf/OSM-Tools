-- Borrowed from osmium project --

create table nodes (
    id INTEGER PRIMARY KEY,
    timestamp TEXT,
    user TEXT,
    lat REAL CHECK ( lat <= 90 AND lat >= -90 ),
    lon REAL CHECK ( lon <= 180 AND lon >= -180 )
);

create index nodes_lat ON nodes ( lat );
create index nodes_lon ON nodes ( lon );

create table node_tags (
    node_id INTEGER REFERENCES nodes ( id ),
    key TEXT,
    value TEXT,
    UNIQUE ( node_id, key, value )
);

-- TODO there should be some sort of 'ON DELETE CASCADE' here

create index node_tags_node_id ON node_tags ( node_id );
create index node_tags_key ON node_tags ( key );

create table ways (
    id INTEGER PRIMARY KEY,
    timestamp TEXT,
    user TEXT
);

create table way_tags (
    way_id INTEGER REFERENCES ways ( id ),
    key TEXT,
    value TEXT,
    UNIQUE ( way_id, key, value )
);

-- TODO there should be some sort of 'ON DELETE CASCADE' here

create index way_tags_way_id ON way_tags ( way_id );
create index way_tags_key ON way_tags ( key );

create table way_nodes (
    way_id INTEGER REFERENCES ways ( id ),
    local_order INTEGER,
    node_id INTEGER REFERENCES nodes ( id ),
    UNIQUE ( way_id, local_order, node_id )
);

-- TODO there should be some sort of 'ON DELETE CASCADE' here

create index way_nodes_way_id ON way_nodes ( way_id );
create index way_nodes_node_id ON way_nodes ( node_id );

create table relations (
    id INTEGER PRIMARY KEY,
    timestamp TEXT,
    user TEXT
);

create table relation_tags (
    relation_id INTEGER REFERENCES relations ( id ),
    key TEXT,
    value TEXT,
    UNIQUE ( relation_id, key, value )
);

-- TODO there should be some sort of 'ON DELETE CASCADE' here

create index relation_tags_relation_id ON relation_tags ( relation_id );
create index relation_tags_key ON relation_tags ( key );

create table relation_members (
    relation_id INTEGER REFERENCES relations ( id ),
    type TEXT CHECK ( type IN ("node", "way", "relation")),
    ref INTEGER,
    role TEXT,
    local_order INTEGER
);

create index relation_members_relation_id ON relation_members ( relation_id );
create index relation_members_type ON relation_members ( type, ref );

    

from sqlalchemy import Column, String

from huggy.database.base import Base, MaterializedBase


class SimilarArtist(MaterializedBase):
    """
    Database model of similar_artist table.
    This table is used to retrieve similar artists from the database.

    """

    def materialized_tables(self):
        return [
            SimilarArtistMv,
            SimilarArtistMvOld,
            SimilarArtistMvTmp,
        ]

    artist_id = Column(String, primary_key=True)
    similar_artists_json_string = Column(String)


class SimilarArtistMv(SimilarArtist, Base):
    __tablename__ = "similar_artist_mv"


class SimilarArtistMvTmp(SimilarArtist, Base):
    __tablename__ = "similar_artist_mv_tmp"


class SimilarArtistMvOld(SimilarArtist, Base):
    __tablename__ = "similar_artist_mv_old"

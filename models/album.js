module.exports = (sequelize, types) =>
  sequelize.define('album', {
    id: { type: types.UUID, primaryKey: true, defaultValue: types.UUIDV4 },
    mbid: { type: types.STRING, notNull: true },

    title: { type: types.STRING, notNull: true },
    date: { type: types.DATEONLY, notNull: true }
  }, {
    timestamps: true,
    paranoid: true,
    underscored: true
  });

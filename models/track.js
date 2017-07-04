module.exports = (sequelize, types) =>
  sequelize.define('Track', {
    id: { type: types.UUID, primaryKey: true, defaultValue: types.UUIDV4 },
    Id: { type: types.STRING, notNull: true }, // mbid

    Title: { type: types.STRING, notNull: true },
    Explicit: { type: types.BOOLEAN }
  }, {
    timestamps: true,
    paranoid: true,
    underscored: true
  });

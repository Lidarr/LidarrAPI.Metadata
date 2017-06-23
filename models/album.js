module.exports = (sequelize, types) =>
  sequelize.define('album', {
    id: { type: types.UUID, primaryKey: true, defaultValue: types.UUIDV4 },

    title: { type: types.STRING, required: true },
    year: { type: types.DATEONLY, required: true }
  }, {
    timestamps: true,
    paranoid: true,
    underscored: true
  });

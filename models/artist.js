module.exports = (sequelize, types) =>
  sequelize.define('artist', {
    id: { type: types.UUID, primaryKey: true, defaultValue: types.UUIDV4 },

    name: { type: types.STRING, required: true }
  }, {
    timestamps: true,
    paranoid: true,
    underscored: true
  });

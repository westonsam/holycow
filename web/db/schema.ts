import { integer, sqliteTable, text } from "drizzle-orm/sqlite-core";

// Only the temporary tunnel address lives here. Evidence and reviews stay on the laptop.
export const laptopConnection = sqliteTable("laptop_connection", {
  id: integer("id").primaryKey(),
  url: text("url").notNull(),
  updated: integer("updated").notNull(),
});

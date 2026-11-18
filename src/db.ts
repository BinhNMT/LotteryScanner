import Database from "better-sqlite3";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const DEFAULT_DB_PATH = resolve(process.cwd(), "lottery_latest.db");
const SCHEMA_PATH = resolve(process.cwd(), "schema.sql");

/**
 * Opens the local SQLite database and ensures the latest-state schema exists.
 */
export function openLotteryDb(dbPath: string = DEFAULT_DB_PATH): Database.Database {
  const db = new Database(dbPath);
  const schemaSql = readFileSync(SCHEMA_PATH, "utf8");
  db.exec(schemaSql);
  return db;
}


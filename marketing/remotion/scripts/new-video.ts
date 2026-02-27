#!/usr/bin/env node

import {cpSync, existsSync, mkdirSync, readdirSync, readFileSync, statSync, writeFileSync} from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import {fileURLToPath} from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const workspaceRoot = path.resolve(__dirname, '..');
const templateDir = path.join(workspaceRoot, 'templates', 'project-base');
const projectsDir = path.join(workspaceRoot, 'projects');
const templateToken = '__PROJECT_NAME__';

const textExtensions = new Set([
  '.md',
  '.json',
  '.ts',
  '.tsx',
  '.js',
  '.mjs',
  '.cjs',
  '.txt',
  '.yml',
  '.yaml',
  '.gitignore',
]);

const helpText = `
Scaffold a new Remotion video project.

Usage:
  npm run new-video -- --name <project-name>

Options:
  --name, -n   Project directory name (required)
  --help, -h   Show this help message

Rules:
  - Allowed characters: lowercase letters, numbers, "-" and "_"
  - Must start with a letter or number
`;

const toError = (value: unknown): Error => {
  if (value instanceof Error) {
    return value;
  }

  return new Error(String(value));
};

const parseProjectName = (argv: string[]): string | null => {
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if ((arg === '--name' || arg === '-n') && i + 1 < argv.length) {
      return argv[i + 1];
    }
  }

  return null;
};

const assertProjectName = (name: string): void => {
  if (!/^[a-z0-9][a-z0-9_-]*$/.test(name)) {
    throw new Error(
      `Invalid project name "${name}". Use lowercase letters, numbers, "-" or "_", and start with a letter/number.`,
    );
  }
};

const shouldProcessAsText = (filePath: string): boolean => {
  const extension = path.extname(filePath);
  if (textExtensions.has(extension)) {
    return true;
  }

  return textExtensions.has(path.basename(filePath));
};

const replaceTokenInTree = (directory: string, replacements: Record<string, string>): void => {
  const entries = readdirSync(directory);
  for (const entry of entries) {
    const fullPath = path.join(directory, entry);
    const entryStat = statSync(fullPath);
    if (entryStat.isDirectory()) {
      replaceTokenInTree(fullPath, replacements);
      continue;
    }

    if (!entryStat.isFile() || !shouldProcessAsText(fullPath)) {
      continue;
    }

    const original = readFileSync(fullPath, 'utf8');
    let next = original;
    for (const [token, value] of Object.entries(replacements)) {
      next = next.split(token).join(value);
    }

    if (next !== original) {
      writeFileSync(fullPath, next, 'utf8');
    }
  }
};

const main = (): void => {
  const args = process.argv.slice(2);

  if (args.includes('--help') || args.includes('-h')) {
    process.stdout.write(helpText.trimStart());
    process.stdout.write('\n');
    return;
  }

  const projectName = parseProjectName(args);
  if (!projectName) {
    throw new Error('Missing --name. Run with --help to see usage.');
  }

  assertProjectName(projectName);

  if (!existsSync(templateDir)) {
    throw new Error(`Template directory not found: ${templateDir}`);
  }

  mkdirSync(projectsDir, {recursive: true});
  const destinationDir = path.join(projectsDir, projectName);
  if (existsSync(destinationDir)) {
    throw new Error(`Target already exists: ${destinationDir}`);
  }

  cpSync(templateDir, destinationDir, {recursive: true, force: false, errorOnExist: true});
  replaceTokenInTree(destinationDir, {[templateToken]: projectName});

  process.stdout.write(`Created project: ${path.relative(workspaceRoot, destinationDir)}\n`);
  process.stdout.write('Next steps:\n');
  process.stdout.write(`  cd ${path.relative(process.cwd(), destinationDir)}\n`);
  process.stdout.write('  npm install\n');
  process.stdout.write('  npm run dev\n');
};

try {
  main();
} catch (error) {
  const err = toError(error);
  process.stderr.write(`new-video failed: ${err.message}\n`);
  process.exitCode = 1;
}

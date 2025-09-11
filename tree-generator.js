const fs = require('fs');
const path = require('path');

function generatePortfolioProjectTree(dir, prefix = '', maxDepth = 4, currentDepth = 0) {
    if (currentDepth >= maxDepth) return '';
    
    const items = fs.readdirSync(dir);
    let result = '';
    
    // Extensiones para proyecto Portfolio Manager (Python/FastAPI + React/TypeScript)
    const portfolioExtensions = [
        // Backend Python
        '.py', '.pyi', '.pyx',
        // Frontend React/TypeScript
        '.ts', '.tsx', '.js', '.jsx',
        // Estilos y assets
        '.css', '.scss', '.sass', '.less',
        // Configuración y datos
        '.json', '.yaml', '.yml', '.toml', '.ini', '.env',
        // Base de datos y migraciones
        '.sql', '.psql', '.alembic',
        // Documentación
        '.md', '.rst', '.txt',
        // Docker y CI/CD
        'Dockerfile', '.dockerignore', '.gitignore',
        // Imágenes y assets
        '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.webp',
        // Otros archivos importantes
        '.lock', '.cfg', '.conf'
    ];
    
    // Carpetas que queremos ignorar (específicas para este proyecto)
    const ignoredItems = [
        '.git', '.vscode', '.idea', '__pycache__', '.pytest_cache',
        'node_modules', '.next', 'dist', 'build',
        '.venv', 'venv', 'env', '.env',
        'Lib', 'Scripts', 'site-packages', '.dist-info',
        'coverage', '.coverage', '.nyc_output',
        '.DS_Store', 'Thumbs.db'
    ];
    
    const filteredItems = items.filter(item => {
        const itemPath = path.join(dir, item);
        
        if (ignoredItems.includes(item)) return false;
        
        // Ignorar archivos que empiecen con punto (excepto algunos importantes)
        if (item.startsWith('.') && !['Dockerfile', '.gitignore', '.dockerignore', '.env.example'].includes(item)) {
            return false;
        }
        
        try {
            const stats = fs.statSync(itemPath);
            
            if (stats.isDirectory()) return true;
            
            const ext = path.extname(item).toLowerCase();
            return portfolioExtensions.includes(ext) || 
                   portfolioExtensions.includes(item) ||
                   item === 'requirements.txt' ||
                   item === 'package.json' ||
                   item === 'pyproject.toml' ||
                   item === 'docker-compose.yml';
        } catch (error) {
            return false;
        }
    });
    
    filteredItems.forEach((item, index) => {
        const itemPath = path.join(dir, item);
        const isLastItem = index === filteredItems.length - 1;
        
        try {
            const stats = fs.statSync(itemPath);
            
            const connector = isLastItem ? '└── ' : '├── ';
            const extension = isLastItem ? '    ' : '│   ';
            
            result += `${prefix}${connector}${item}\n`;
            
            if (stats.isDirectory()) {
                result += generatePortfolioProjectTree(
                    itemPath, 
                    prefix + extension, 
                    maxDepth, 
                    currentDepth + 1
                );
            }
        } catch (error) {
            // Ignorar archivos que no se pueden leer
        }
    });
    
    return result;
}

function getPortfolioProjectStats(dir) {
    let stats = { 
        python: 0, 
        typescript: 0, 
        javascript: 0,
        react: 0,
        sql: 0,
        config: 0,
        docs: 0,
        folders: 0 
    };
    
    function countFiles(directory, maxDepth = 10, currentDepth = 0) {
        if (currentDepth >= maxDepth) return;
        
        try {
            const items = fs.readdirSync(directory);
            
            items.forEach(item => {
                const itemPath = path.join(directory, item);
                
                try {
                    const fileStat = fs.statSync(itemPath);
                    
                    if (fileStat.isDirectory() && 
                        !item.startsWith('.') && 
                        !['node_modules', '.venv', 'venv', '__pycache__', 'Lib', 'site-packages'].includes(item)) {
                        stats.folders++;
                        countFiles(itemPath, maxDepth, currentDepth + 1);
                    } else if (fileStat.isFile()) {
                        const ext = path.extname(item).toLowerCase();
                        
                        switch (ext) {
                            case '.py':
                            case '.pyi':
                                stats.python++; 
                                break;
                            case '.ts':
                                stats.typescript++; 
                                break;
                            case '.tsx':
                                stats.react++; 
                                break;
                            case '.js':
                            case '.jsx':
                                stats.javascript++; 
                                break;
                            case '.sql':
                            case '.psql':
                                stats.sql++; 
                                break;
                            case '.json':
                            case '.yaml':
                            case '.yml':
                            case '.toml':
                            case '.env':
                                stats.config++; 
                                break;
                            case '.md':
                            case '.rst':
                            case '.txt':
                                stats.docs++; 
                                break;
                        }
                        
                        // Archivos especiales
                        if (['requirements.txt', 'package.json', 'pyproject.toml', 'docker-compose.yml'].includes(item)) {
                            stats.config++;
                        }
                    }
                } catch (error) {
                    // Ignorar archivos que no se pueden leer
                }
            });
        } catch (error) {
            // Ignorar directorios que no se pueden leer
        }
    }
    
    countFiles(dir);
    return stats;
}

// Información del proyecto
const projectPath = process.argv[2] || '.';
const projectName = path.basename(path.resolve(projectPath));

console.log(`\n🏛️  ${projectName}/ (Portfolio Management System)`);
console.log('📊 Python FastAPI + React TypeScript\n');
console.log(generatePortfolioProjectTree(projectPath));

// Estadísticas del proyecto
const stats = getPortfolioProjectStats(projectPath);
console.log('\n📈 Estadísticas del proyecto:');
console.log(`    🐍 Python files: ${stats.python}`);
console.log(`    ⚛️  React/TSX: ${stats.react}`);
console.log(`    📘 TypeScript: ${stats.typescript}`);
console.log(`    📙 JavaScript: ${stats.javascript}`);
console.log(`    🗄️  SQL files: ${stats.sql}`);
console.log(`    ⚙️  Config files: ${stats.config}`);
console.log(`    📚 Documentation: ${stats.docs}`);
console.log(`    📁 Folders: ${stats.folders}`);

// Detectar fase del proyecto basado en archivos existentes
console.log('\n🚀 Estado del proyecto:');
const hasBackend = fs.existsSync(path.join(projectPath, 'backend'));
const hasFrontend = fs.existsSync(path.join(projectPath, 'frontend'));
const hasDockerCompose = fs.existsSync(path.join(projectPath, 'docker-compose.yml'));
const hasDatabase = fs.existsSync(path.join(projectPath, 'backend', 'alembic'));
const hasAPI = fs.existsSync(path.join(projectPath, 'backend', 'app', 'main.py'));

if (hasBackend && hasFrontend && hasDockerCompose && hasDatabase && hasAPI) {
    console.log('    ✅ Fase 2-3: Sistema funcional con rebalancing');
} else if (hasBackend && hasAPI && hasDockerCompose) {
    console.log('    🟡 Fase 1: MVP básico en desarrollo');
} else if (hasBackend) {
    console.log('    🟠 Fase 1: Setup inicial completado');
} else {
    console.log('    🔴 Fase 0: Estructura inicial');
}

// Sugerencias basadas en el estado actual
console.log('\n💡 Próximos pasos sugeridos:');
if (!hasBackend) {
    console.log('    1. Crear estructura backend/app/');
    console.log('    2. Setup FastAPI con main.py');
    console.log('    3. Configurar PostgreSQL con Docker');
} else if (!hasAPI) {
    console.log('    1. Crear backend/app/main.py');
    console.log('    2. Setup modelos de datos');
    console.log('    3. Implementar ETL básico');
} else if (!hasDatabase) {
    console.log('    1. Setup Alembic para migraciones');
    console.log('    2. Crear modelos de PostgreSQL');
    console.log('    3. Implementar TimescaleDB');
} else if (!hasFrontend) {
    console.log('    1. Setup React con TypeScript');
    console.log('    2. Crear dashboard básico');
    console.log('    3. Conectar con API backend');
}

// Guardar archivo
const timestamp = new Date().toISOString().split('T')[0];
const filename = `portfolio-structure-${timestamp}.txt`;
const output = `${projectName}/ (Portfolio Management System)
Python FastAPI + React TypeScript

${generatePortfolioProjectTree(projectPath)}

📈 Estadísticas:
   🐍 Python: ${stats.python} | ⚛️ React: ${stats.react} | 📘 TS: ${stats.typescript} | 🗄️ SQL: ${stats.sql} | 📁 Folders: ${stats.folders}

Generated: ${new Date().toLocaleString()}`;

fs.writeFileSync(filename, output);
console.log(`\n💾 Estructura guardada en: ${filename}`);

// Ejecutar con: node tree-generator.js [ruta-opcional]
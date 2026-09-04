/**
 * This is a minimal config.
 *
 * If you need the full config, get it from here:
 * https://unpkg.com/browse/tailwindcss@latest/stubs/defaultConfig.stub.js
 */

module.exports = {
    content: {
        files: [
            /**
             * HTML. Paths to Django template files that will contain Tailwind CSS classes.
             */

            /*  Templates within theme app (<tailwind_app_name>/templates), e.g. base.html. */
            '../templates/**/*.html',

            /*
             * Main templates directory of the project (BASE_DIR/templates).
             * Adjust the following line to match your project structure.
             */
            '../../templates/**/*.html',

            /*
             * Templates in other django apps (BASE_DIR/<any_app_name>/templates).
             * Adjust the following line to match your project structure.
             */
            '../../**/templates/**/*.html',

            /**
             * JS: If you use Tailwind CSS in JavaScript, uncomment the following lines and make sure
             * patterns match your project structure.
             */
            /* JS 1: Ignore any JavaScript in node_modules folder. */
            // '!../../**/node_modules',
            /* JS 2: Process all JavaScript files in the project. */
            // '../../**/*.js',

            /**
             * Python: If you use Tailwind CSS classes in Python, uncomment the following line
             * and make sure the pattern below matches your project structure.
             */
            // '../../**/*.py'
        ],
        /**
         * Extrator customizado para Django: remove os tags {% %} e {{ }} ANTES de
         * extrair candidatos. Sem isso, uma classe colada num tag (ex. "bg-[#7fe3c4]/90{%")
         * vira um candidato único que o Tailwind não consegue parsear e a classe é
         * silenciosamente omitida do CSS compilado (bug clássico Django + Tailwind).
         * Mantém o mesmo comportamento do extrator padrão em todo o resto.
         */
        extract: {
            html: (content) => {
                let limpo = content
                    .replace(/\/\*.*?\*\//g, '')
                    .replace(/\{%-?[\s\S]*?-?%\}/g, ' ')
                    .replace(/\{\{-?[\s\S]*?-?\}\}/g, ' ')
                    .replace(/class\s*=\s*/gi, '')
                let largas = limpo.match(/[^<>"'`\s]*[^<>"'`\s:]/g) || []
                let internas = limpo.match(/[^<>"'`\s.(){}[\]#=%:][^<>"'`\s(){}[\]#=%]*/g) || []
                return largas.concat(internas)
            },
        },
    },
    theme: {
        extend: {
            colors: {
                /* Design system GEOD-CEOD — tokens de cor piano azul-marinho. */
                hazon: {
                    night: '#0a1e3d',      /* fundo base piano */
                    abyss: '#081830',      /* header / superfícies mais escuras */
                    deep: '#0f2a52',       /* gradiente de fundo */
                    surface: '#0e2540',    /* superfícies escuras (cartões sólidos) */
                    mid: '#0c2245',        /* gradiente de fundo */
                    primary: '#1a5fb4',
                    'primary-dark': '#1450a0',
                    accent: '#5b8def',
                    text: '#f4fafb',
                    muted: '#bcd3da',
                    dim: '#a6bfc7',
                    success: '#4ade80',
                    'success-bright': '#22c55e',
                    warn: '#fbbf24',
                    danger: '#fca5a5',
                    info: '#93b8f7',
                    orange: '#fb923c',
                    blue: '#5b8def',
                    slate: '#94a3b8',
                    pink: '#f472b6',
                },
            },
            fontFamily: {
                sans: ['Manrope', 'Segoe UI', 'sans-serif'],
                display: ['Fraunces', 'Georgia', 'serif'],
                mono: ['JetBrains Mono', 'monospace'],
            },
            boxShadow: {
                'glow-accent': '0 0 8px rgba(91,141,239,0.44)',
                'glow-warn': '0 0 8px rgba(251,191,36,0.44)',
                'accent-lg': '0 10px 30px -12px rgba(91,141,239,0.35)',
                soft: '0 8px 30px -12px rgba(0,0,0,0.40)',
            },
        },
    },
    plugins: [
        /**
         * '@tailwindcss/forms' is the forms plugin that provides a minimal styling
         * for forms. If you don't like it or have own styling for forms,
         * comment the line below to disable '@tailwindcss/forms'.
         */
        require('@tailwindcss/forms'),
        require('@tailwindcss/typography'),
        require('@tailwindcss/aspect-ratio'),
    ],
}

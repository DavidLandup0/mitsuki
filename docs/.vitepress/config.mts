import { defineConfig } from 'vitepress'

// https://vitepress.dev/reference/site-config
export default defineConfig({
  title: "Mitsuki",
  description: "Python's flexibility and productivity, Spring Boot's battle-tested enterprise patterns.",
  themeConfig: {
    // https://vitepress.dev/reference/default-theme-config
    nav: [
      { text: 'Home', link: '/' },
      { text: 'Documentation', link: '/examples' }
    ],

    sidebar: [
      {
        text: 'Documentation',
        items: [
          { text: 'Overview', link: '/01_overview' },
          { text: 'Decorators', link: '/02_decorators' },
          { text: 'Repositories', link: '/03_repositories' },
          { text: 'Controllers', link: '/04_controllers' },
          { text: 'Profiles', link: '/05_profiles' },
          { text: 'Configuration', link: '/06_configuration' },
          { text: 'CLI', link: '/07_cli' },
          { text: 'Database Queries', link: '/08_database_queries' },
          { text: 'Response Entity', link: '/09_response_entity' },
          { text: 'Request/Response Validation', link: '/10_request_response_validation' },
          { text: 'JSON Serialization', link: '/11_json_serialization' },
          { text: 'Logging', link: '/12_logging' },
          { text: 'File Uploads', link: '/13_file_uploads' },
          { text: 'Scheduled Tasks', link: '/14_scheduled_tasks' },
          { text: 'Metrics', link: '/15_metrics' },
          { text: 'OpenAPI', link: '/16_openapi' },
          { text: 'Database', link: '/17_database' },
          { text: 'Dockerizing Mitsuki', link: '/18_dockerizing_mitsuki' },
        ]
      }
    ],

    socialLinks: [
      { icon: 'github', link: 'https://github.com/vuejs/vitepress' }
    ]
  }
})

"""Response schemas for compliance validation."""

COMPLIANCE_SCHEMAS = {
    "compliance_validation": [
        {
            "name": "réponse_LLM",
            "description": """Classification finale de l'offre commerciale
            selon les règles de conformité.
            Les valeurs possibles sont 'ACCEPTED', si l'offre répond à toutes les règles
            de conformité, 'REJECTED', si elle enfreint au moins une règle et
            'UNDETERMINED' s'il y a le moindre doute.
            En cas d'incertitude, il est préférable de classifier en UNDETERMINED plutôt
            que de risquer une mauvaise décision.""",
            "type": "string",
        },
        {
            "name": "explication_classification",
            "description": """Explication détaillée de la raison pour laquelle l'offre a
            été classée comme ACCEPTED, REJECTED ou UNDETERMINED. Doit spécifiquement
            faire référence à la ou les règles de conformité concernées et expliquer
            comment l'offre s'y rapporte.""",
            "type": "string",
        },
        {
            "name": "score_conformite",
            "description": """Score de conformité global de l'offre sur une échelle de
            0 à 100, où 100 signifie une conformité totale avec toutes les règles et 0
            une non-conformité totale.""",
            "type": "float",
        },
        {
            "name": "regles_violees",
            "description": """Liste les numéros des règles violées. Doit prendre la
            forme d'une liste d'integer faisant référence au numéro de la règle
            enfreinte. Si l'offre n'enfreint aucune règle, indiquer [].""",
            "type": "list",
        },
        {
            "name": "points_amelioration",
            "description": """Suggestions concises pour améliorer la conformité de
            l'offre si elle est classée comme 'REJECTED'. Proposer des actions
            spécifiques que l'acteur culturel pourrait entreprendre pour rendre son
            offre conforme. 'Non applicable' si l'offre est conforme.""",
            "type": "string",
        },
    ],
    # ajouter verif prix
}

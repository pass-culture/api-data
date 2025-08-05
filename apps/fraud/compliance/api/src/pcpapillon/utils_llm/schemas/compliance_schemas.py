"""Response schemas for compliance validation."""

COMPLIANCE_SCHEMAS = {
    "compliance_validation": [
        {
            "name": "reponse_LLM",
            "description": """Classification finale de l'offre commerciale
            selon les règles de conformité.
            Les valeurs possibles sont 'approved', si l'offre répond à toutes les règles
            de conformité, 'rejected', si elle enfreint au moins une règle et
            'undetermined' s'il y a le moindre doute.
            En cas d'incertitude, il est préférable de classifier en undetermined plutôt
            que de risquer une mauvaise décision.""",
            "type": "string",
        },
        {
            "name": "explication_classification",
            "description": """Explication détaillée de la raison pour laquelle l'offre a
            été classée comme approved, rejected ou undetermined. Doit spécifiquement
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
            l'offre si elle est classée comme 'rejected'. Proposer des actions
            spécifiques que l'acteur culturel pourrait entreprendre pour rendre son
            offre conforme. 'Non applicable' si l'offre est conforme.""",
            "type": "string",
        },
        {
            "name": "prix_participation",
            "description": """Recherche dans la description et le last_stock_price
            le prix total du produit. Prends seulement en compte le prix du produit
            global. Si l'offre concerne une participation à l'achat, le prix global
            correspond à la somme du montant de la participation du pass Culture et
            du reste à charge à payer. Additionne dans ce cas le last_stock_price et le
            reste à payer pour obtenir le prix total du produit.""",
            "type": "string",
        }
    ],
    "verification_prix_participation": [
        {
            "name": "recapitulatif_prix_trouvés",
            "description": """Recherche le prix à la vente du produit sur les sites
            de références donnés, et si disponible, le site fabriquant.
            Récapitule les prix trouvés pour chaque site, indique le prix et le
            lien""",
            "type": "string",
        },
        {
            "name": "prix_moyen",
            "description": """Calcule à partir de ces résultats le prix moyen et dis
            moi s'il diverge, et si applicable de combien en %,
            du prix proposé chez nous""",
            "type": "string",
        },
        {
            "name": "pourcentage_divergence_prix",
            "description": """Indique le pourcentage de divergence du prix proposé sur
            le pass Culture (Prix_participation) par rapport au prix moyen calculé à
            partir des résultats de recherche. La formule utilisée est :
            (prix_proposé - prix_moyen) / prix_moyen * 100.
            Indique simplement le résultat.""",
            "type": "float",
        },
        {
            "name": "liens_source",
            "description": """Pour chaque prix trouvé, donne moi le lien vers la
            page du produit sur le site de référence""",
            "type": "string",
        },
    ],
}

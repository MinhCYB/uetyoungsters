import demoProfile from '../../demo/demo_profile.json';

export function createDemoSession(){
  const basic=demoProfile.basic_information;
  return {
    displayName:demoProfile.session.display_name,
    assessmentCompleted:true,
    profileStatus:'confirmed',
    selectedCareerId:demoProfile.session.selected_career_id,
    answers:{
      assessmentId:demoProfile.assessment.assessment_id,
      questionSetId:demoProfile.assessment.question_set_id,
      responses:demoProfile.assessment.sample_answers,
      basic:{
        name:demoProfile.session.display_name,
        level:basic.current_stage,
        major:basic.major,
        region:basic.preferred_region,
        weeklyHours:basic.weekly_learning_hours,
        relocation:basic.willing_to_relocate?'Sẵn sàng chuyển nơi ở':'Ưu tiên không chuyển nơi ở',
        trainingRoutes:basic.accepted_training_routes,
      },
      interests:demoProfile.interest_profile.top_groups,
      interestCurrent:demoProfile.interest_profile.current_activities,
      interestExploration:demoProfile.interest_profile.exploration_activities,
      careerValues:demoProfile.interest_profile.career_values,
      skills:demoProfile.self_reported_skills.map(skill=>({name:skill.name,level:skill.level,context:skill.context})),
    },
    aiAnalysis:{
      riasec:demoProfile.interest_profile.riasec_scores,
      habitPatterns:demoProfile.habit_patterns,
      workTendencies:demoProfile.work_tendencies,
      experiences:demoProfile.experiences,
      abilities:demoProfile.ability_analysis.map(item=>({
        abilityId:item.ability_id,
        abilityName:item.ability_name,
        level:item.level,
        score:item.score,
        confidence:item.confidence,
        evidenceQuestionIds:item.evidence_question_ids,
        reasoning:item.reasoning,
      })),
      careers:demoProfile.career_recommendations.map(item=>({
        id:item.id,title:item.title,reason:item.reason,matchScore:item.match_score,skillGaps:item.skill_gaps,
      })),
      roadmaps:[{
        targetCareer:{id:demoProfile.roadmap.target_career_id},
        title:demoProfile.roadmap.title,
        weeklyHours:demoProfile.roadmap.weekly_hours,
        milestones:demoProfile.roadmap.milestones,
      }],
    },
    abilityAdjustments:null,
    abilityReviewed:false,
    demoFixtureId:demoProfile.fixture.id,
  };
}
